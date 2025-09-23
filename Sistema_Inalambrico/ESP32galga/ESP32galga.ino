#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include <WiFi.h>
#include <SD.h>
#include <SPI.h>
#include "time.h"

// ================= CONFIG WIFI =================
const char* ssid     = "Bastos";      // <-- pon tu WiFi
const char* password = "Bastos05";  // <-- pon tu WiFi

// Servidores NTP y zona horaria (Costa Rica = UTC-6 sin DST)
const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = -6 * 3600;
const int daylightOffset_sec = 0;

// ================= CONFIG SD (tu esquema) =================
#define SD_CS 5
#define SCK   19
#define MISO  18
#define MOSI  23 

// ================= CONFIG STRAIN =================
Adafruit_ADS1115 ads;

const float FACTOR_CAL = 433.46f;    // µε por (mV/V)
const float V_EXC = 5.0f;            // Voltaje excitación

const uint8_t PIN_BOTON = 17; // Botón Start/Stop
const uint8_t PIN_BOTON_TARE  = 4;   // Botón TARE
const uint8_t PIN_LED   = 16;

bool isMeasuring = true;
bool needsTare   = true;
float offsetStrain = 0.0f;

// Debounce
unsigned long lastDebounceTime = 0;
int lastButtonReading = HIGH;

// Debounce TARE
unsigned long lastDebounceTimeTARE = 0;
int lastButtonReadingTARE = HIGH;


const unsigned long DEBOUNCE_MS = 50;
// Muestreo
const unsigned long SAMPLE_INTERVAL_MS = 100;
unsigned long lastSampleTime = 0;
unsigned long sampleCount = 0;

bool sd_ready = false; // variable para rastrear el estado de la SD
String currentFileName = "";

void setup() {
  Serial.begin(115200);
  pinMode(PIN_BOTON, INPUT_PULLUP);
  pinMode(PIN_BOTON_TARE, INPUT_PULLUP);
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, isMeasuring ? HIGH : LOW);

  // ==== WiFi ====
  WiFi.begin(ssid, password);
  Serial.print("Conectando a WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi conectado!");

  // ==== NTP ====
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  Serial.println("Sincronizando hora con NTP...");
  delay(2000);  // darle chance a sincronizar
  imprimirHoraActual();

  // ==== ADS1115 ====
  if (!ads.begin(0x48)) {
    Serial.println("Error inicializando ADS1115");
    while (1) delay(1000);
  }
  ads.setGain(GAIN_SIXTEEN);
  Serial.println("ADS1115 listo");

  // ==== SD ====
  Serial.println("Inicializando SD...");
  SPI.begin(SCK, MISO, MOSI, SD_CS);
  if (!SD.begin(SD_CS)) {
    Serial.println("⚠ Error al inicializar SD. No se guardarán datos.");
    sd_ready = false;
  } else {
    Serial.println("SD detectada!");
    sd_ready = true;

    // Generar un nombre de archivo único
    String fileName = "/datos.csv";
    int fileIndex = 1;
    while (SD.exists(fileName.c_str())) {
      fileName = "/datos" + String(fileIndex++) + ".csv";
      if (fileIndex > 999) { // Límite para evitar un bucle infinito
        Serial.println("No se pudo encontrar un nombre de archivo disponible.");
        sd_ready = false;
        return;
      }
    }
    
    // Abrir el nuevo archivo para escribir el encabezado
    File dataFile = SD.open(fileName.c_str(), FILE_WRITE);
    if (dataFile) {
      currentFileName = fileName;
      dataFile.println("Fecha,Hora,Muestra,Strain_compensado,Strain_bruto,Tension_V");
      dataFile.close();
      Serial.print("Nuevo archivo creado: ");
      Serial.println(currentFileName);
    } else {
      Serial.println("Error al abrir o crear el archivo.");
      sd_ready = false;
    }
    
  }
}

void loop() {
  handleButtonDebounce();   // Botón Start/Stop
  handleButtonTare();       // Botón TARE
  checkSerialCommands();    // Comandos por Serial

  unsigned long now = millis();
  if (isMeasuring && (now - lastSampleTime >= SAMPLE_INTERVAL_MS)) {
    lastSampleTime = now;

    float bruto = medirStrain();
    float comp  = bruto - offsetStrain;
    float vdiff = medirVoltaje();

    mostrarEnSerial(comp, bruto, vdiff);
    // Llama a guardarEnSD solo si la tarjeta SD está lista
    if (sd_ready) {
      guardarEnSD(comp, bruto, vdiff);
    }
  }
}

void checkSerialCommands() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 't' || c == 'T') realizarTare();
    else if (c == 's' || c == 'S') toggleMedicion();
    else if (c == 'o' || c == 'O') {
      Serial.print("Offset actual: ");
      Serial.print(offsetStrain, 4);
      Serial.println(" µε");
    } else if (c == '?') {
      Serial.println("Comandos disponibles:");
      Serial.println("t: tare (calibrar a cero)");
      Serial.println("s: start/stop medición");
      Serial.println("o: mostrar offset");
    }
  }
}

// ================= FUNCIONES =================

void imprimirHoraActual() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    Serial.println("⚠ Error obteniendo hora");
    return;
  }
  Serial.printf("Hora actual: %02d/%02d/%04d %02d:%02d:%02d\n",
                timeinfo.tm_mday, timeinfo.tm_mon + 1, timeinfo.tm_year + 1900,
                timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec);
}

// ================= FUNCIONES BOTONES =================

void handleButtonDebounce() {
  int reading = digitalRead(PIN_BOTON);
  if (reading != lastButtonReading) {
    lastDebounceTime = millis();
    lastButtonReading = reading;
  } else {
    if ((millis() - lastDebounceTime) > DEBOUNCE_MS) {
      if (reading == LOW) {
        toggleMedicion();
        while (digitalRead(PIN_BOTON) == LOW) delay(10); // Esperar a que suelte
      }
    }
  }
}

void handleButtonTare() {
  int reading = digitalRead(PIN_BOTON_TARE);
  if (reading != lastButtonReadingTARE) {
    lastDebounceTimeTARE = millis();
    lastButtonReadingTARE = reading;
  } else {
    if ((millis() - lastDebounceTimeTARE) > DEBOUNCE_MS) {
      if (reading == LOW) {
        realizarTare();
        while (digitalRead(PIN_BOTON_TARE) == LOW) delay(10); // Esperar a que suelte
      }
    }
  }
}

void toggleMedicion() {
  isMeasuring = !isMeasuring;
  digitalWrite(PIN_LED, isMeasuring ? HIGH : LOW);
  Serial.print("Medición ");
  Serial.println(isMeasuring ? "REANUDADA" : "PAUSADA");
}

void realizarTare() {
  Serial.println("Realizando TARE...");
  const int N = 40;
  float s = 0.0f;
  for (int i = 0; i < N; ++i) {
    s += medirStrain();
    delay(25);
  }
  offsetStrain = s / N;
  needsTare = false;
  Serial.print("TARE completo. Offset = ");
  Serial.print(offsetStrain, 4);
  Serial.println(" µε");
}

float medirStrain() {
  int16_t raw = ads.readADC_Differential_0_1();
  float vdiff = ads.computeVolts(raw); // V
  float mV_per_V = (vdiff / V_EXC) * 1000.0f;
  return mV_per_V * FACTOR_CAL;
}

float medirVoltaje() {
  int16_t raw = ads.readADC_Differential_0_1();
  return ads.computeVolts(raw);
}

void mostrarEnSerial(float comp, float bruto, float vdiff) {
  Serial.print("Strain: ");
  Serial.print(comp, 2);
  Serial.print(" µε | Vdiff: ");
  Serial.print(vdiff, 6);
  Serial.print(" V | Bruto: ");
  Serial.print(bruto, 2);
  Serial.print(" µε | Muestra ");
  Serial.println(sampleCount);
  sampleCount++;
}

void guardarEnSD(float comp, float bruto, float vdiff) {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) return;

  // Abre el archivo en modo de añadir (APPEND)
  File dataFile = SD.open(currentFileName.c_str(), FILE_APPEND);
  if (dataFile) {
    char fecha[12], hora[10];
    strftime(fecha, sizeof(fecha), "%d/%m/%Y", &timeinfo);
    strftime(hora,  sizeof(hora),  "%H:%M:%S", &timeinfo);

    dataFile.print(fecha);
    dataFile.print(",");
    dataFile.print(hora);
    dataFile.print(",");
    dataFile.print(sampleCount);
    dataFile.print(",");
    dataFile.print(comp, 4);
    dataFile.print(",");
    dataFile.print(bruto, 4);
    dataFile.print(",");
    dataFile.println(vdiff, 6);
    
    // Cierra el archivo inmediatamente para asegurar que los datos se escriban
    dataFile.close();
  } else {
    // Si la apertura falla, informa al usuario con el nombre correcto del archivo
    Serial.print("⚠ Error al abrir ");
    Serial.print(currentFileName);
    Serial.println(" para escritura.");
}
}

