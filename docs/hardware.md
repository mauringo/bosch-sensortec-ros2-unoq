# Hardware and wiring

[Back to the project](../README.md) · [Quick start](../README.md#run-it-in-arduino-app-lab)

## The tested prototype

I did not have a fancy ready-to-use sensor module, so I used what I had: a **BMI088 Shuttle Board 3.0 on an adapter board**, connected as a prototype. Yes, the setup is a bit of a wiring mess. It is enough to explore the software path, and it is the hardware behind these results.

<p align="center">
  <a href="images/bmi088-shuttle-board-adapter-enhanced.png">
    <img src="images/bmi088-shuttle-board-adapter-enhanced.png" width="640" alt="AI-enhanced overview of the BMI088 Shuttle Board 3.0 and green adapter board used in the personal Arduino UNO Q project">
  </a>
</p>

*AI-enhanced overview of my adapter and BMI088 shuttle board. [Original photo](images/originals/bmi088-adapter-original.png). Use the original and the module documentation for pin labels and wiring; enhanced lettering may differ.*

### Online examples of BMI088 modules

For a tidier build, a ready-made **BMI088 breakout** can replace the shuttle-board-and-adapter arrangement. Here are online examples using the same BMI088 sensor as this project. Check the module's connector and I²C settings: a Grove connector or pin header needs suitable wiring/an adapter to reach the UNO Q's Qwiic bus.

| BMI088 module | Interface / format | What to check for this app |
| --- | --- | --- |
| [Seeed Studio Grove — 6-Axis Accelerometer & Gyroscope (BMI088)](https://www.seeedstudio.com/Grove-6-Axis-Accelerometer-Gyroscope-BMI088.html) | I²C module with a Grove connector | Use appropriate Grove-to-Qwiic wiring/an adapter. Seeed documents default addresses `0x19` / `0x69`; match the sketch's address settings to the module. |
| [Boardoza BMI088 6-Axis IMU Breakout Board](https://github.com/Boardoza/Boardoza_BMI088_6-Axis_IMU_Breakout_Board) | SPI / I²C breakout with header connections | Its documentation specifies SPI by default and JP1 for I²C selection. JP2 selects `0x19` / `0x69` or `0x18` / `0x68`. Follow its pinout when wiring to Qwiic. |
| [BobbieBots BMI088 I²C breakout](https://www.tindie.com/products/bobbiebots/bmi088-i2c-breakout/) | Compact I²C breakout | Check the module's pinout and provide matching power, SDA and SCL wiring. [Hardware files and documentation](https://github.com/simondlevy/bmi088-i2c-breakout). |

These links point to maker documentation for **BMI088 modules only**. The alternatives have not been tested with this repository; the demonstrated setup is my shuttle board and adapter. Check current availability with the maker, use the UNO Q's 3.3 V I²C connections, and confirm addresses before using a different module.

### Arduino UNO Q to BMI088 pinout and I²C connections

Arduino's [UNO Q manual](https://docs.arduino.cc/tutorials/uno-q/user-manual/) identifies the Qwiic bus as `Wire1` and specifies **3.3 V** Qwiic operation.

| Connection / setting | This project |
| --- | --- |
| I²C bus | Qwiic connector, `Wire1` |
| Bus clock | 400 kHz |
| BMI088 accelerometer address | `0x18` |
| BMI088 gyroscope address | `0x68` |
| Sensor library | [Bolder Flight Systems BMI088 **1.0.1**](https://github.com/bolderflight/bmi088-arduino/tree/v1.0.1), unchanged; pinned in [`sketch/sketch.yaml`](../sketch/sketch.yaml) |
| Physical quantities | Acceleration in m/s², angular velocity in rad/s, temperature in °C |

Connect the corresponding 3.3 V supply, ground, SDA and SCL signals using your module's documentation. Check its I²C/SPI selection, address jumpers and pull-ups. If its addresses differ, edit `BMI088_ACCEL_ADDR` and `BMI088_GYRO_ADDR` in [the sketch](../sketch/sketch.ino). The pictured adapter is not a universal pinout guide.

