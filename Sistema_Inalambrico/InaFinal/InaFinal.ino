// Código para conexión de un ESP32 con un adc, reloj en tiempo real y módulo de memoria 
// para generar una lectura de una galga extensiométrica

// Estructura base generada por GeminiAI
// Código de lectura y guardado de microSD tomado de Wemos:
// https://github.com/wemos/D1_mini_Examples/blob/master/examples/04.Shields/Micro_SD_Shield/Datalogger/Datalogger.ino
// Correción de Errores con Deepseek.AI

#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include <RtcDS1302.h>
#include <SD.h>
#include <SPI.h>

// ================= CONFIG RTC DS1302 =================
#define DS1302_RST_PIN 14
#define DS1302_DAT_PIN 12
#define DS1302_CLK_PIN 13

// descomentar siguiente linea para configurar el reloj con fecha actual
// #define CONFIGURAR_RTC_PRIMERA_VEZ 

ThreeWire myWire(DS1302_DAT_PIN, DS1302_CLK_PIN, DS1302_RST_PIN);
RtcDS1302<ThreeWire> Rtc(myWire);

// ================= CONFIG SD CARD =================
#define SD_CS 5 
#define SD_SCK 18  
#define SD_MISO 19 
#define SD_MOSI 22  
File dataFile;
String LOG_FILENAME = "/datos.csv";  // Cambiado a String para nombres dinámicos

// ================= CONFIG STRAIN =================
Adafruit_ADS1115 ads;

const float FACTOR_CAL = 433.46f;
const float V_EXC = 5.0f;

const uint8_t PIN_BOTON_STOP = 16;
const uint8_t PIN_BOTON_TARE = 17;
const uint8_t PIN_LED = 4;

bool isMeasuring = true;
bool needsTare = true;
float offsetStrain = 0.0f;

const unsigned long DEBOUNCE_MS = 50;
const unsigned long SAMPLE_INTERVAL_MS = 1000;
unsigned long lastSampleTime = 0;
unsigned long sampleCount = 0;

unsigned long lastDebounceTime = 0;
int lastButtonReading = HIGH;
unsigned long lastDebounceTimeTARE = 0;
int lastButtonReadingTARE = HIGH;

bool sd_ready = false;

// ================= PROTOTIPOS DE FUNCIONES =================
void imprimirHoraActual();
void toggleMedicion();
void realizarTare();
float medirStrain();
float medirVoltaje();
void mostrarEnSerial(float comp, float bruto, float vdiff);
void guardarEnSD(float comp, float vdiff);
void handleButtonDebounce();
void handleButtonTare();
void checkSerialCommands();
String generarNombreArchivoUnico();

void setup() {
  Serial.begin(115200);
  
  // Configuración de pines
  pinMode(PIN_BOTON_STOP, INPUT_PULLUP);
  pinMode(PIN_BOTON_TARE, INPUT_PULLUP);
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, isMeasuring ? HIGH : LOW);

  // ==== Inicialización SD Card ====
  Serial.println("Inicializando SD...");
  
  // Configurar SPI con los pines específicos
  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  
  if (!SD.begin(SD_CS)) {
    Serial.println("Error al inicializar SD. No se guardarán datos.");
    sd_ready = false;
  } else {
    Serial.println("SD detectada!");
    sd_ready = true;
    
    // Generar un nombre de archivo único
    LOG_FILENAME = generarNombreArchivoUnico();
    
    if (LOG_FILENAME == "") {
      Serial.println("No se pudo crear un nombre de archivo único.");
      sd_ready = false;
    } else {
      Serial.print("Archivo de datos: ");
      Serial.println(LOG_FILENAME);
      
      // Crear archivo CSV con encabezados
      dataFile = SD.open(LOG_FILENAME.c_str(), FILE_WRITE);
      if (dataFile) {
        dataFile.println("TIMESTAMP,RECORD,Strain,Vstrain");
        dataFile.close();
        Serial.println("Archivo CSV creado con encabezados.");
      } else {
        Serial.println("Error al crear archivo CSV.");
        sd_ready = false;
      }
    }
  }
  
  // ==== I2C y ADS1115 ====
  
  Wire.begin(21, 23);
  if (!ads.begin(0x48)) {
    Serial.println("Error inicializando ADS1115");
    while (1) delay(1000);
  }
  ads.setGain(GAIN_SIXTEEN);
  Serial.println("ADS1115 listo");
  
  // ==== DS1302 RTC ====
  Serial.println("Inicializando RTC DS1302...");
  Rtc.Begin();

  if (!Rtc.IsDateTimeValid()) {
    Serial.println("RTC: Hora NO válida o pila agotada.");
    if (Rtc.GetIsWriteProtected()) {
      Serial.println("RTC: Deshabilitando protección de escritura.");
      Rtc.SetIsWriteProtected(false);
    }
  }

  #ifdef CONFIGURAR_RTC_PRIMERA_VEZ
  Rtc.SetDateTime(RtcDateTime(__DATE__, __TIME__));
  Serial.println("✓ RTC configurado con hora de compilación.");
  #endif

  imprimirHoraActual();

  Serial.println("\n========================================");
  Serial.println("  Inicialización completa. Listo para medir.");
  Serial.println("  Comandos: t=tare, s=stop/start, o=offset");
  Serial.println("========================================\n");
}

void loop() {
  handleButtonDebounce();
  handleButtonTare();
  checkSerialCommands();

  unsigned long now = millis();
  if (isMeasuring && (now - lastSampleTime >= SAMPLE_INTERVAL_MS)) {
    lastSampleTime = now;

    float bruto = medirStrain();
    float comp = bruto - offsetStrain;
    float vdiff = medirVoltaje();

    mostrarEnSerial(comp, bruto, vdiff);

    if (sd_ready) {
      guardarEnSD(comp, vdiff);
    }
  }
}

// ================= FUNCIÓN PARA GENERAR NOMBRE ÚNICO =================
String generarNombreArchivoUnico() {
  String fileName = "/datos.csv";
  int fileIndex = 1;
  
  while (SD.exists(fileName.c_str())) {
    fileName = "/datos" + String(fileIndex++) + ".csv";
    if (fileIndex > 99) { // Límite para evitar un bucle infinito
      Serial.println("No se pudo encontrar un nombre de archivo disponible.");
      return "";
    }
  }
  
  return fileName;
}

// ================= FUNCIONES DE SD CARD =================
void guardarEnSD(float comp, float vdiff) {
  if (!Rtc.IsDateTimeValid()) {
    Serial.println("No se puede guardar: RTC inválido");
    return;
  }
  
  RtcDateTime now = Rtc.GetDateTime();
  
  dataFile = SD.open(LOG_FILENAME.c_str(), FILE_APPEND);
  if (dataFile) {
    // Formato: "2/9/2025  22:06:40"
    char timestamp[30];
    snprintf(timestamp, sizeof(timestamp), "%d/%d/%04d  %02d:%02d:%02d",
             now.Day(), now.Month(), now.Year(),
             now.Hour(), now.Minute(), now.Second());
    
    // Escribir línea en formato CSV
    dataFile.print(timestamp);
    dataFile.print(",");
    dataFile.print(sampleCount);
    dataFile.print(",");
    dataFile.print(comp, 4);
    dataFile.print(",");
    dataFile.println(vdiff, 6);
    
    dataFile.close();
    
    // Mensaje de confirmación cada 10 muestras
    if (sampleCount % 10 == 0) {
      Serial.println("Datos guardados en SD");
    }
  } else {
    Serial.println("Error al abrir archivo para escritura");
  }
}

// ================= FUNCIONES AUXILIARES =================
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
      Serial.println("\n===== COMANDOS DISPONIBLES =====");
      Serial.println("t: Realizar tare (calibrar a cero)");
      Serial.println("s: Start/Stop medición");
      Serial.println("o: Mostrar offset actual");
      Serial.println("?: Mostrar esta ayuda");
      Serial.println("================================\n");
    }
  }
}

void imprimirHoraActual() {
  if (!Rtc.IsDateTimeValid()) {
    Serial.println("Error obteniendo hora. RTC NO válido.");
    return;
  }
  RtcDateTime now = Rtc.GetDateTime();
  Serial.printf("Hora actual: %02d/%02d/%04d %02d:%02d:%02d\n",
                now.Day(), now.Month(), now.Year(),
                now.Hour(), now.Minute(), now.Second());
}

void handleButtonDebounce() {
  int reading = digitalRead(PIN_BOTON_STOP);
  if (reading != lastButtonReading) {
    lastDebounceTime = millis();
    lastButtonReading = reading;
  } else {
    if ((millis() - lastDebounceTime) > DEBOUNCE_MS) {
      if (reading == LOW) {
        toggleMedicion();
        while (digitalRead(PIN_BOTON_STOP) == LOW) delay(10);
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
        while (digitalRead(PIN_BOTON_TARE) == LOW) delay(10);
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
  Serial.println("⚙ Realizando TARE...");
  const int N = 40;
  float s = 0.0f;
  for (int i = 0; i < N; ++i) {
    s += medirStrain();
    delay(25);
  }
  offsetStrain = s / N;
  needsTare = false;
  Serial.print("✓ TARE completo. Offset = ");
  Serial.print(offsetStrain, 4);
  Serial.println(" µε");
}

float medirStrain() {
  int16_t raw = ads.readADC_Differential_0_1();
  float vdiff = ads.computeVolts(raw);
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
  Serial.print(" µε | Muestra #");
  Serial.println(sampleCount);
  sampleCount++;
}