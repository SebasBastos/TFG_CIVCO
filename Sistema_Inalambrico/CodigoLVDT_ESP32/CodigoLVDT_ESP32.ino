// Código para conexión de un ESP32 con un adc, reloj en tiempo real y módulo de memoria 
// para generar una lectura de un LVDT

// Estructura base generada por GeminiAI
// Código de lectura y guardado de microSD tomado de Wemos:
// https://github.com/wemos/D1_mini_Examples/blob/master/examples/04.Shields/Micro_SD_Shield/Datalogger/Datalogger.ino
// Correción de Errores con Deepseek.AI

#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include <SD.h>
#include <SPI.h>
#include <ThreeWire.h>
#include <RtcDS1302.h>

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
#define SCK 18
#define MISO 19
#define MOSI 23
File dataFile;
String LOG_FILENAME = "/datos.csv";  // Nombre dinámico

// ================= CONFIG SENSOR =================
Adafruit_ADS1115 ads;
const float SENSITIVITY = 90.73; // mV/mm - AJUSTAR según tu certificado de calibración

// ================= CONFIG BOTONES Y LED =================
const uint8_t PIN_BOTON_STOP = 16;
const uint8_t PIN_BOTON_TARE = 17;
const uint8_t PIN_LED = 4;

// ================= VARIABLES GLOBALES =================
unsigned long recordCount = 0;
bool sdInitialized = false;
bool measurementRunning = true;
float zeroOffset = 0.0;
bool newMeasurement = true;

// Debounce para botones
const unsigned long DEBOUNCE_MS = 50;
unsigned long lastDebounceTime = 0;
int lastButtonReading = HIGH;
unsigned long lastDebounceTimeTARE = 0;
int lastButtonReadingTARE = HIGH;

// Intervalo de muestreo
const unsigned long SAMPLE_INTERVAL_MS = 1000;
unsigned long lastSampleTime = 0;

// ================= PROTOTIPOS DE FUNCIONES =================
void checkSerialCommands();
void performZeroCalibration();
void printHelp();
void printDateTime(const RtcDateTime& dt);
void handleButtonDebounce();
void handleButtonTare();
void toggleMedicion();
String generarNombreArchivoUnico();

void setup() {
  Serial.begin(115200);
  
  // Configuración de pines
  pinMode(PIN_BOTON_STOP, INPUT_PULLUP);
  pinMode(PIN_BOTON_TARE, INPUT_PULLUP);
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, measurementRunning ? HIGH : LOW);
  
  // Inicializar I2C
  Wire.begin(21, 22); // SDA=GPIO21, SCL=GPIO22
  
  // ==== Inicializar RTC ====
  Serial.println("Inicializando RTC...");
  Rtc.Begin();
  
  if (!Rtc.IsDateTimeValid()) {
    Serial.println("⚠ RTC perdió la configuración...");
    #ifdef CONFIGURAR_RTC_PRIMERA_VEZ
    Rtc.SetDateTime(RtcDateTime(__DATE__, __TIME__));
    #endif
  }

  if (Rtc.GetIsWriteProtected()) {
    Serial.println("RTC: Deshabilitando protección de escritura...");
    Rtc.SetIsWriteProtected(false);
  }

  if (!Rtc.GetIsRunning()) {
    Serial.println("RTC no estaba funcionando, iniciando...");
    Rtc.SetIsRunning(true);
  }

  // Mostrar hora actual
  if (Rtc.IsDateTimeValid()) {
    RtcDateTime now = Rtc.GetDateTime();
    Serial.print("✓ Hora actual: ");
    printDateTime(now);
    Serial.println();
  }

  // ==== Inicializar ADS1115 ====
  Serial.println("Inicializando ADS1115...");
  if (!ads.begin(0x48)) {
    Serial.println("⚠ Error al inicializar ADS1115!");
    while (1) delay(1000);
  }
  
  ads.setGain(GAIN_ONE); // ±4.096V
  Serial.println("✓ ADS1115 inicializado correctamente");

  // ==== Inicializar tarjeta SD ====
  Serial.println("Inicializando SD...");
  SPI.begin(SCK, MISO, MOSI, SD_CS);
  
  if (!SD.begin(SD_CS)) {
    Serial.println("⚠ Error al inicializar SD. No se guardarán datos.");
    sdInitialized = false;
  } else {
    Serial.println("✓ SD detectada!");
    sdInitialized = true;
    
    // Generar un nombre de archivo único
    LOG_FILENAME = generarNombreArchivoUnico();
    
    if (LOG_FILENAME == "") {
      Serial.println("⚠ No se pudo crear un nombre de archivo único.");
      sdInitialized = false;
    } else {
      Serial.print("✓ Archivo de datos: ");
      Serial.println(LOG_FILENAME);
      
      // Crear archivo CSV con encabezados
      dataFile = SD.open(LOG_FILENAME.c_str(), FILE_WRITE);
      if (dataFile) {
        dataFile.println("TIMESTAMP,RECORD,disp_mm");
        dataFile.close();
        Serial.println("✓ Archivo CSV creado con encabezados.");
      } else {
        Serial.println("⚠ Error al crear archivo CSV.");
        sdInitialized = false;
      }
    }
  }

  // Mostrar comandos disponibles
  printHelp();
  
  Serial.println("\n========================================");
  Serial.println("  Sistema listo. Iniciando adquisición...");
  Serial.println("========================================\n");
  delay(1000);
}

void loop() {
  // Manejar botones
  handleButtonDebounce();
  handleButtonTare();
  
  // Verificar comandos del serial
  checkSerialCommands();
  
  // Solo tomar mediciones si está en ejecución
  unsigned long now = millis();
  if (measurementRunning && (now - lastSampleTime >= SAMPLE_INTERVAL_MS)) {
    lastSampleTime = now;
    
    // Leer fecha y hora actual
    RtcDateTime nowTime = Rtc.GetDateTime();
    
    // Leer valor del ADS1115 (canal diferencial 0-1)
    int16_t adc0 = ads.readADC_Differential_0_1();
    
    // Convertir a voltaje
    float volts = ads.computeVolts(adc0);
    
    // Convertir voltaje a desplazamiento en mm (con offset de calibración)
    float raw_displacement_mm = (1.0 / SENSITIVITY) * (volts * 1000.0);
    float calibrated_displacement_mm = raw_displacement_mm - zeroOffset;
    
    // Formatear timestamp
    char timestamp[20];
    snprintf(timestamp, sizeof(timestamp), "%04d-%02d-%02d %02d:%02d:%02d",
             nowTime.Year(), nowTime.Month(), nowTime.Day(),
             nowTime.Hour(), nowTime.Minute(), nowTime.Second());

    // Mostrar datos por serial
    Serial.printf("📊 #%lu - %s: %.3f mm (Raw: %.3f mm, V: %.3f V)\n", 
                  recordCount, timestamp, calibrated_displacement_mm, raw_displacement_mm, volts);

    // Guardar en SD si está disponible
    if (sdInitialized) {
      dataFile = SD.open(LOG_FILENAME.c_str(), FILE_APPEND);
      if (dataFile) {
        dataFile.printf("%s,%lu,%.3f\n", timestamp, recordCount, calibrated_displacement_mm);
        dataFile.close();
        
        // Mensaje de confirmación cada 10 muestras
        if (recordCount % 10 == 0) {
          Serial.println("✓ Datos guardados en SD");
        }
      } else {
        Serial.println("⚠ Error al abrir archivo para escritura!");
      }
    }

    // Si es nueva medición después de pausa, agregar marcador
    if (newMeasurement) {
      if (sdInitialized) {
        dataFile = SD.open(LOG_FILENAME.c_str(), FILE_APPEND);
        if (dataFile) {
          dataFile.println("# Mediciones reanudadas");
          dataFile.close();
        }
      }
      newMeasurement = false;
    }

    recordCount++;
  }
}

// ================= FUNCIÓN PARA GENERAR NOMBRE ÚNICO =================
String generarNombreArchivoUnico() {
  String fileName = "/datos.csv";
  int fileIndex = 1;
  
  while (SD.exists(fileName.c_str())) {
    fileName = "/datos" + String(fileIndex++) + ".csv";
    if (fileIndex > 99) {
      Serial.println("⚠ No se pudo encontrar un nombre de archivo disponible.");
      return "";
    }
  }
  
  return fileName;
}

// ================= MANEJO DE BOTONES =================
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
        performZeroCalibration();
        while (digitalRead(PIN_BOTON_TARE) == LOW) delay(10);
      }
    }
  }
}

void toggleMedicion() {
  measurementRunning = !measurementRunning;
  digitalWrite(PIN_LED, measurementRunning ? HIGH : LOW);
  
  if (measurementRunning) {
    Serial.println("▶ Mediciones REANUDADAS");
    newMeasurement = true;
  } else {
    Serial.println("⏸ Mediciones PAUSADAS");
    if (sdInitialized) {
      dataFile = SD.open(LOG_FILENAME.c_str(), FILE_APPEND);
      if (dataFile) {
        dataFile.println("# Mediciones pausadas");
        dataFile.close();
      }
    }
  }
}

// ================= COMANDOS SERIAL =================
void checkSerialCommands() {
  if (Serial.available() > 0) {
    char command = Serial.read();
    
    switch (command) {
      case 's':
      case 'S':
        toggleMedicion();
        break;
        
      case 't':
      case 'T':
        performZeroCalibration();
        break;

      default:
        Serial.println("Comando no reconocido. Presiona 'h' para ayuda.");
        break;
    }
    
    // Limpiar buffer serial
    while (Serial.available() > 0) {
      Serial.read();
    }
  }
}

void performZeroCalibration() {
  Serial.println("⚙ Iniciando calibración a cero...");
  Serial.println("   Midiendo valor actual (espera 3 segundos)...");
  
  // Tomar múltiples lecturas para promediar
  int samples = 10;
  float sum = 0;
  
  for (int i = 0; i < samples; i++) {
    int16_t adc0 = ads.readADC_Differential_0_1();
    float volts = ads.computeVolts(adc0);
    float displacement_mm = (1.0 / SENSITIVITY) * (volts * 1000.0);
    sum += displacement_mm;
    delay(300);
  }
  
  float averageDisplacement = sum / samples;
  zeroOffset = averageDisplacement;
  
  Serial.println("✅ Calibración completada!");
  Serial.printf("   Valor medido: %.3f mm\n", averageDisplacement);
  Serial.printf("   Offset establecido: %.3f mm\n", zeroOffset);
  Serial.println("   Nuevas mediciones mostrarán desplazamiento relativo a este punto.");
  
  // Guardar evento de calibración en SD
  if (sdInitialized) {
    dataFile = SD.open(LOG_FILENAME.c_str(), FILE_APPEND);
    if (dataFile) {
      RtcDateTime now = Rtc.GetDateTime();
      char timestamp[20];
      snprintf(timestamp, sizeof(timestamp), "%04d-%02d-%02d %02d:%02d:%02d",
               now.Year(), now.Month(), now.Day(),
               now.Hour(), now.Minute(), now.Second());
      dataFile.printf("# Calibración a cero: %s - Offset: %.3f mm\n", timestamp, zeroOffset);
      dataFile.close();
    }
  }
}

void printHelp() {
  Serial.println("\n===== COMANDOS DISPONIBLES =====");
  Serial.println("s - Pausar/Reanudar mediciones (también BOTÓN STOP)");
  Serial.println("t - Calibración a cero/tarar (también BOTÓN TARE)");
  Serial.println("================================\n");
}

void printDateTime(const RtcDateTime& dt) {
  char datestring[20];
  snprintf(datestring, 
           sizeof(datestring),
           "%04d-%02d-%02d %02d:%02d:%02d",
           dt.Year(), 
           dt.Month(),
           dt.Day(), 
           dt.Hour(), 
           dt.Minute(), 
           dt.Second());
  Serial.print(datestring);
}
