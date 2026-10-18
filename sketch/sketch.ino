#include <Arduino.h>
#include <Wire.h>
#include <BMI088.h>
#include <Arduino_RouterBridge.h>
#include <Arduino_LED_Matrix.h>
#include <math.h>
#include <array>

// The BMI088 library reads/scales the sensor exactly as before.
// Bridge sends a compact numeric IMU packet at high speed, while temperature
// and the matrix use a slower cache refreshed once every two seconds.

// =====================================================
// BMI088 configuration
// =====================================================

enum class Filter { WIDE, NORMAL, SMOOTH };
struct ImuSettings {
    uint16_t rateHz;
    uint8_t accelRangeG;
    uint16_t gyroRangeDps;
    Filter filter;
};

// EDIT THIS ONE LINE: requested Hz, acceleration ±g, rotation ±deg/s, filter.
constexpr ImuSettings IMU = {100, 6, 500, Filter::NORMAL};
// Rates: 1..1600 (target, not guaranteed). Accel: 3/6/12/24 g.
// Gyro: 125/250/500/1000/2000 deg/s. Filter: WIDE / NORMAL / SMOOTH.
static_assert(IMU.rateHz >= 1 && IMU.rateHz <= 1600, "Rate must be 1..1600 Hz");
static_assert(IMU.accelRangeG == 3 || IMU.accelRangeG == 6 || IMU.accelRangeG == 12 || IMU.accelRangeG == 24,
              "Accel range must be 3, 6, 12 or 24 g");
static_assert(IMU.gyroRangeDps == 125 || IMU.gyroRangeDps == 250 || IMU.gyroRangeDps == 500 ||
              IMU.gyroRangeDps == 1000 || IMU.gyroRangeDps == 2000,
              "Gyro range must be 125, 250, 500, 1000 or 2000 deg/s");
static_assert(IMU.filter == Filter::WIDE || IMU.filter == Filter::NORMAL || IMU.filter == Filter::SMOOTH,
              "Filter must be WIDE, NORMAL or SMOOTH");

#define BMI088_ACCEL_ADDR 0x18
#define BMI088_GYRO_ADDR  0x68

// Qwiic port on UNO Q = Wire1
Bmi088Accel accel(Wire1, BMI088_ACCEL_ADDR);
Bmi088Gyro gyro(Wire1, BMI088_GYRO_ADDR);

bool imuReady = false;
Arduino_LED_Matrix matrix;
float temperatureC = NAN;
unsigned long lastInitAttempt = 0;
unsigned long lastMatrixUpdate = 0;
constexpr unsigned long TEMPERATURE_INTERVAL_MS = 2000;
unsigned long lastTemperatureRead = 0;
unsigned long lastImuRead = 0;
bool hasImuSample = false;
float imuValues[6] = {};

unsigned long lastSerialPrint = 0;

#define SERIAL_PRINT_INTERVAL 500  // milliseconds

// Select a hardware output rate at least as high as the requested ROS rate.
uint16_t accelOdrHz() {
    const uint16_t rates[] = {25, 50, 100, 200, 400, 800, 1600};
    for (uint16_t rate : rates) if (IMU.rateHz <= rate) return rate;
    return 1600;
}

uint16_t gyroOdrHz() {
    if (IMU.rateHz <= 100) return 100;
    if (IMU.rateHz <= 200) return 200;
    if (IMU.rateHz <= 400) return 400;
    if (IMU.rateHz <= 1000) return 1000;
    return 2000;
}

uint16_t accelBandwidthHz() {
    const uint16_t bandwidths[][3] = {
        {10, 5, 3}, {20, 9, 5}, {40, 19, 10}, {80, 38, 20},
        {145, 75, 40}, {230, 140, 80}, {280, 234, 145}
    };
    int row = 0;
    for (uint16_t rate = 25; rate < accelOdrHz(); rate *= 2) row++;
    return bandwidths[row][(int)IMU.filter];
}

uint16_t gyroBandwidthHz() {
    switch (gyroOdrHz()) {
        case 100: return IMU.filter == Filter::SMOOTH ? 12 : 32;
        case 200: return IMU.filter == Filter::SMOOTH ? 23 : 64;
        case 400: return 47;
        case 1000: return 116;
        default: return IMU.filter == Filter::WIDE ? 532 : 230;
    }
}

const char* filterName() {
    if (IMU.filter == Filter::WIDE) return "WIDE";
    if (IMU.filter == Filter::SMOOTH) return "SMOOTH";
    return "NORMAL";
}

bool configureIMU() {
    Bmi088Accel::Range accelRange = Bmi088Accel::RANGE_6G;
    switch (IMU.accelRangeG) {
        case 3: accelRange = Bmi088Accel::RANGE_3G; break;
        case 6: break;
        case 12: accelRange = Bmi088Accel::RANGE_12G; break;
        case 24: accelRange = Bmi088Accel::RANGE_24G; break;
    }
    Bmi088Gyro::Range gyroRange = Bmi088Gyro::RANGE_500DPS;
    switch (IMU.gyroRangeDps) {
        case 125: gyroRange = Bmi088Gyro::RANGE_125DPS; break;
        case 250: gyroRange = Bmi088Gyro::RANGE_250DPS; break;
        case 500: break;
        case 1000: gyroRange = Bmi088Gyro::RANGE_1000DPS; break;
        case 2000: gyroRange = Bmi088Gyro::RANGE_2000DPS; break;
    }
    Bmi088Accel::Odr accelOdr = Bmi088Accel::ODR_100HZ_BW_19HZ;
    // The library orders each group of three as WIDE, NORMAL, SMOOTH.
    switch (accelOdrHz()) {
        case 25: accelOdr = Bmi088Accel::ODR_25HZ_BW_10HZ; break;
        case 50: accelOdr = Bmi088Accel::ODR_50HZ_BW_20HZ; break;
        case 100: accelOdr = Bmi088Accel::ODR_100HZ_BW_40HZ; break;
        case 200: accelOdr = Bmi088Accel::ODR_200HZ_BW_80HZ; break;
        case 400: accelOdr = Bmi088Accel::ODR_400HZ_BW_145HZ; break;
        case 800: accelOdr = Bmi088Accel::ODR_800HZ_BW_230HZ; break;
        default: accelOdr = Bmi088Accel::ODR_1600HZ_BW_280HZ; break;
    }
    accelOdr = static_cast<Bmi088Accel::Odr>((int)accelOdr + (int)IMU.filter);
    Bmi088Gyro::Odr gyroOdr = Bmi088Gyro::ODR_100HZ_BW_32HZ;
    switch (gyroOdrHz()) {
        case 100: gyroOdr = IMU.filter == Filter::SMOOTH ? Bmi088Gyro::ODR_100HZ_BW_12HZ : Bmi088Gyro::ODR_100HZ_BW_32HZ; break;
        case 200: gyroOdr = IMU.filter == Filter::SMOOTH ? Bmi088Gyro::ODR_200HZ_BW_23HZ : Bmi088Gyro::ODR_200HZ_BW_64HZ; break;
        case 400: gyroOdr = Bmi088Gyro::ODR_400HZ_BW_47HZ; break;
        case 1000: gyroOdr = Bmi088Gyro::ODR_1000HZ_BW_116HZ; break;
        default: gyroOdr = IMU.filter == Filter::WIDE ? Bmi088Gyro::ODR_2000HZ_BW_532HZ : Bmi088Gyro::ODR_2000HZ_BW_230HZ; break;
    }
    return accel.setRange(accelRange) && gyro.setRange(gyroRange) &&
           accel.setOdr(accelOdr) && gyro.setOdr(gyroOdr);
}

String imu_config() {
    String json = "{\"rate_hz\":" + String(IMU.rateHz);
    json += ",\"accel_range_g\":" + String(IMU.accelRangeG);
    json += ",\"gyro_range_dps\":" + String(IMU.gyroRangeDps);
    json += ",\"filter\":\"" + String(filterName()) + "\"";
    json += ",\"accel_odr_hz\":" + String(accelOdrHz());
    json += ",\"gyro_odr_hz\":" + String(gyroOdrHz());
    json += ",\"accel_bandwidth_hz\":" + String(accelBandwidthHz());
    json += ",\"gyro_bandwidth_hz\":" + String(gyroBandwidthHz());
    json += ",\"fast_protocol\":1,\"temperature_interval_ms\":2000";
    json += ",\"ready\":" + String(imuReady ? "true" : "false") + "}";
    return json;
}

// =====================================================
// I2C scanner
// =====================================================

void scanI2C() {

    Serial.println("\nScanning Qwiic I2C bus...");

    for (uint8_t address = 1; address < 127; address++) {

        Wire1.beginTransmission(address);

        if (Wire1.endTransmission() == 0) {

            Serial.print("Found I2C device: 0x");

            if (address < 16) Serial.print("0");

            Serial.println(address, HEX);
        }
    }

    Serial.println("I2C scan complete.\n");
}

// =====================================================
// Initialize BMI088
// =====================================================

void initIMU() {

    lastInitAttempt = millis();

    Serial.println("Initializing BMI088...");

    int accelStatus = accel.begin();
    int gyroStatus = gyro.begin();

    Serial.print("Accelerometer initialization: ");
    Serial.println(accelStatus);

    Serial.print("Gyroscope initialization: ");
    Serial.println(gyroStatus);

    imuReady = (accelStatus > 0 && gyroStatus > 0);
    hasImuSample = false;
    temperatureC = NAN;
    if (imuReady) imuReady = configureIMU();

    if (imuReady) {

        Serial.println("BMI088 initialized successfully!");
        Serial.println(imu_config());

    } else {

        Serial.println("ERROR: BMI088 initialization failed!");
    }
}

// =====================================================
// Original analog sensor
// =====================================================

int read_a0() {
    return analogRead(A0);
}

// =====================================================
// Read IMU through RouterBridge
// =====================================================

bool acquireImu() {
    if (!imuReady) return false;
    // Keep the existing Bolder Flight library and its units/axis transforms.
    accel.readSensor();
    gyro.readSensor();
    imuValues[0] = accel.getAccelX_mss();
    imuValues[1] = accel.getAccelY_mss();
    imuValues[2] = accel.getAccelZ_mss();
    imuValues[3] = gyro.getGyroX_rads();
    imuValues[4] = gyro.getGyroY_rads();
    imuValues[5] = gyro.getGyroZ_rads();
    hasImuSample = true;
    lastImuRead = millis();
    return true;
}

// Native MessagePack array, avoiding JSON and float-to-text conversion.
// [ok, target Hz, ax, ay, az, gx, gy, gz], in m/s² and rad/s.
std::array<float, 8> read_imu_fast() {
    if (!acquireImu()) return {0, float(IMU.rateHz), 0, 0, 0, 0, 0, 0};
    return {1, float(IMU.rateHz), imuValues[0], imuValues[1], imuValues[2],
            imuValues[3], imuValues[4], imuValues[5]};
}

// Low-rate console requests reuse the latest sample without extra sensor reads.
std::array<float, 9> read_imu_cached() {
    if (!imuReady || ((!hasImuSample || millis() - lastImuRead >= 500) && !acquireImu())) {
        return {0, float(IMU.rateHz), 0, 0, 0, 0, 0, 0, 0};
    }
    return {1, float(IMU.rateHz), imuValues[0], imuValues[1], imuValues[2],
            imuValues[3], imuValues[4], imuValues[5], temperatureC};
}

float acceleration(uint8_t axis) {
    return imuValues[axis];
}

float rotation(uint8_t axis) {
    return imuValues[axis + 3];
}

float read_temperature() {
    // Return the slow cache; this RPC never triggers an additional sensor read.
    return imuReady ? temperatureC : NAN;
}

String read_imu() {

    // Compatibility for older Python code. New clients use numeric packets.
    // Console reads share the latest fast sample. Still work without ROS.
    if (!imuReady || ((!hasImuSample || millis() - lastImuRead >= 500) && !acquireImu())) {
        return "{\"ok\":false}";
    }

    String json = "{";

    json += "\"ok\":true,";
    json += "\"rate_hz\":" + String(IMU.rateHz) + ",";

    json += "\"ax\":" + String(acceleration(0), 6) + ",";
    json += "\"ay\":" + String(acceleration(1), 6) + ",";
    json += "\"az\":" + String(acceleration(2), 6) + ",";

    json += "\"gx\":" + String(rotation(0), 6) + ",";
    json += "\"gy\":" + String(rotation(1), 6) + ",";
    json += "\"gz\":" + String(rotation(2), 6) + ",";

    json += "\"temperature\":" +
            String(temperatureC, 2);

    json += "}";

    return json;
}

// =====================================================
// IMU status
// =====================================================

bool imu_status() {
    return imuReady;
}

// =====================================================
// Serial Monitor measurements
// =====================================================

void checkImuConnection() {

    if (!imuReady) return;

    // readSensor() returns void, so retain the periodic bus health check.
    Wire1.beginTransmission(BMI088_ACCEL_ADDR);
    bool accelResponding = Wire1.endTransmission() == 0;
    Wire1.beginTransmission(BMI088_GYRO_ADDR);
    bool gyroResponding = Wire1.endTransmission() == 0;
    if (!accelResponding || !gyroResponding) {
        imuReady = false;
        hasImuSample = false;
        temperatureC = NAN;
        Serial.println("BMI088 disconnected; initialization will be retried.");
        return;
    }
}

void printIMU() {
    // Serial output uses cached samples; suppress it at high target rates.
    if (!imuReady || IMU.rateHz >= 100 || !hasImuSample) return;

    Serial.println("========== BMI088 ==========");

    Serial.print("Accel X: ");
    Serial.print(acceleration(0), 3);

    Serial.print("  Y: ");
    Serial.print(acceleration(1), 3);

    Serial.print("  Z: ");
    Serial.print(acceleration(2), 3);

    Serial.println(" m/s2");

    Serial.print("Gyro X:  ");
    Serial.print(rotation(0), 4);

    Serial.print("  Y: ");
    Serial.print(rotation(1), 4);

    Serial.print("  Z: ");
    Serial.print(rotation(2), 4);

    Serial.println(" rad/s");

    Serial.print("Temperature: ");
    Serial.print(temperatureC, 2);
    Serial.println(" C");

    Serial.println("============================\n");
}

// Compact 3x5 digits fit "25C" on the UNO Q's 13x8 matrix.
// Wider values scroll one column at a time, without delay() or blocking RPC.
const uint8_t DIGITS[10][5] = {
    {7, 5, 5, 5, 7}, {2, 6, 2, 2, 7}, {7, 1, 7, 4, 7},
    {7, 1, 7, 1, 7}, {5, 5, 7, 1, 1}, {7, 4, 7, 1, 7},
    {7, 4, 7, 5, 7}, {7, 1, 1, 1, 1}, {7, 5, 7, 5, 7},
    {7, 5, 7, 1, 7}
};

void showTemperature() {
    static uint8_t pixels[104];
    static String previousText;
    static int scrollColumn = 0;
    String text = (imuReady && isfinite(temperatureC))
        ? String((int)roundf(temperatureC)) + "C" : "--";
    // A static value needs no redraw. Longer values still advance their scroll.
    if (!(text != previousText) && text.length() <= 3) return;
    if (text != previousText) {
        scrollColumn = 0;
        previousText = text;
    }
    memset(pixels, 0, sizeof(pixels));
    int width = text.length() * 4 - 1;
    int startX = width <= 13 ? (13 - width) / 2 : 13 - scrollColumn;
    for (unsigned int index = 0; index < text.length(); index++) {
        char character = text[index];
        for (int row = 0; row < 5; row++) {
            uint8_t bits = 0;
            if (character >= '0' && character <= '9') bits = DIGITS[character - '0'][row];
            else if (character == 'C') bits = (row == 0 || row == 4) ? 7 : 4;
            else if (character == '-' && row == 2) bits = 7;
            for (int column = 0; column < 3; column++) {
                int x = startX + (int)index * 4 + column;
                if (x >= 0 && x < 13 && (bits & (1 << (2 - column)))) {
                    pixels[(row + 1) * 13 + x] = 1;
                }
            }
        }
    }
    matrix.draw(pixels);
    if (width > 13) scrollColumn = (scrollColumn + 1) % (width + 14);
}

// =====================================================
// Setup
// =====================================================

void setup() {

    Serial.begin(115200);
    matrix.begin();
    matrix.setGrayscaleBits(1);
    showTemperature();

    delay(1000);

    Serial.println();
    Serial.println("================================");
    Serial.println("Arduino UNO Q + Bosch BMI088");
    Serial.println("ROS 2 Jazzy / RouterBridge");
    Serial.println("================================");

    // Initialize Qwiic I2C
    Wire1.begin();
    Wire1.setClock(400000);

    delay(100);

    // Scan I2C bus
    scanI2C();

    // Initialize BMI088
    initIMU();

    // Start Arduino RouterBridge
    Bridge.begin();

    // Register services
    Bridge.provide_safe("read_a0", read_a0);
    Bridge.provide_safe("read_imu", read_imu);
    Bridge.provide_safe("read_imu_fast", read_imu_fast);
    Bridge.provide_safe("read_imu_cached", read_imu_cached);
    Bridge.provide_safe("read_temperature", read_temperature);
    Bridge.provide_safe("imu_status", imu_status);
    Bridge.provide_safe("imu_config", imu_config);

    Serial.println("RouterBridge initialized.");
    Serial.println("Starting IMU measurements...");
}

// =====================================================
// Main loop
// =====================================================

void loop() {

    if (!imuReady && millis() - lastInitAttempt >= 5000) {
        initIMU();
    }

    if (imuReady && (!isfinite(temperatureC) || millis() - lastTemperatureRead >= TEMPERATURE_INTERVAL_MS)) {
        lastTemperatureRead = millis();
        // Keep the matrix useful even when no Linux client is requesting IMU data.
        if (!hasImuSample || millis() - lastImuRead >= TEMPERATURE_INTERVAL_MS) acquireImu();
        // The library still reads its internal temperature with readSensor().
        // Only this cached value is exposed to the matrix/Bridge every 2 seconds.
        temperatureC = accel.getTemperature_C();
    }

    if (millis() - lastMatrixUpdate >= 150) {
        lastMatrixUpdate = millis();
        showTemperature();
    }

    if (millis() - lastSerialPrint >= SERIAL_PRINT_INTERVAL) {

        lastSerialPrint = millis();

        checkImuConnection();
        printIMU();
    }
}
