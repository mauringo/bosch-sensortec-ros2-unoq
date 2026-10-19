# Sharing the BMI088 / ROS 2 Jazzy project

[Back to the project](../README.md)

## GitHub About and topics

Suggested About description:

> ROS 2 Jazzy integration for Bosch Sensortec BMI088 on Arduino UNO Q using App Lab and RouterBridge.

Topics are stored in [github-topics.json](github-topics.json). They describe the working implementation: BMP581 is planned, and this project does not use micro-ROS. GitHub topics help people discover related repositories; there is no promised ranking or traffic increase. See [GitHub's topic documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics).

These files do not automatically change GitHub's About panel. A repository administrator can edit it with the gear next to About, or run the following from the repository root with an authenticated GitHub CLI:

```bash
gh repo edit mauringo/bosch-sensortec-ros2-unoq --description 'ROS 2 Jazzy integration for Bosch Sensortec BMI088 on Arduino UNO Q using App Lab and RouterBridge.'
gh api --method PUT repos/mauringo/bosch-sensortec-ros2-unoq/topics --input docs/github-topics.json
```

The topics command replaces the topic list. Review and preserve any additional relevant topics before running it.

## Social preview

Open [repository settings](https://github.com/mauringo/bosch-sensortec-ros2-unoq/settings), then **Social preview → Edit → Upload an image**.

The existing [prototype JPEG](images/uno-q-bmi088-project-preview.jpg) is an available option: 1368 × 1506 pixels, 495,097 bytes. It fits GitHub's file-size limit but is portrait, so inspect the preview for cropping. The current 4:3 [README cover](images/uno-q-bmi088-cover.png) is over 2 MB and exceeds that limit; it needs a smaller export before use as a GitHub social preview. For a later purpose-made landscape card, GitHub recommends 1280 × 640 pixels and a file under 1 MB. See [GitHub's social preview requirements](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview).

For announcement posts, pair a real hardware photo with the unaltered ROS output. Keep the README's AI-enhanced illustrations labeled if you use them. No click-through percentage is claimed.

## Where to share, in suggested order

| Channel | Suggested angle |
| --- | --- |
| [Open Robotics Discourse — Projects](https://discourse.ros.org/c/ros-projects/10) | Reproducible BMI088-to-ROS 2 path, standard topics, observed delivery rate and timing limitations. The [category introduction](https://discourse.ros.org/t/about-the-projects-category/175) invites project presentations. |
| [Arduino Forum — UNO Q](https://forum.arduino.cc/c/official-hardware/uno-family/uno-q/222) | App Lab, `Wire1`, RouterBridge and the custom-Brick source-reload workaround. Ask for reports from other UNO Q setups. |
| [Arduino Project Hub](https://projecthub.arduino.cc/) | A full tutorial with parts, wiring, deployment steps and real output. Follow its [project guidelines](https://projecthub.arduino.cc/guidelines). |
| [Hackster.io](https://www.hackster.io/) | A build log with hardware photos and a short demo; the site already hosts [UNO Q and ROS 2 projects](https://www.hackster.io/naveenbskumar/ball-chasing-quadruped-robot-with-ros-2-arduino-uno-q-cf9701). |
| [r/ROS](https://www.reddit.com/r/ROS/) | A concise technical demo and a specific question about Bridge throughput or sensor timestamps. Check the community's current posting rules before submitting. |
| LinkedIn | A short demo showing the board and live topics, with the repository link and an invitation to reproduce the setup. |

Use upstream library Discussions only if an existing showcase or project-sharing thread is available. Do not open a support issue just to advertise the repository. Link the pinned library as an acknowledgement, not as a way to manufacture backlinks.

## Draft: ROS Discourse

**Title:** BMI088 IMU on Arduino UNO Q with ROS 2 Jazzy, App Lab and RouterBridge

I've put together a personal open-source integration that reads a Bosch Sensortec BMI088 on the Arduino UNO Q's STM32 and publishes ROS 2 Jazzy messages on its Linux side.

The data path is BMI088 → I²C / Wire1 → STM32 → RouterBridge → a custom ROS 2 Brick. It publishes acceleration and angular velocity on `/imu/data_raw`, plus sensor die temperature on `/imu/temperature` every two seconds. The sketch uses the unchanged Bolder Flight Systems BMI088 1.0.1 library.

The supplied subscriber logs show approximately 65–68 Hz with a 100 Hz target in one run. This is an observation from my setup, not a controlled benchmark. Orientation is unavailable, timestamps reflect Linux receipt time, and calibration and acquisition timestamps remain future work.

The repository includes wiring, App Lab deployment instructions, a listener, and a workaround for local custom-Brick Python edits continuing to run from an old container image.

Code, hardware photos and actual ROS output:
https://github.com/mauringo/bosch-sensortec-ros2-unoq

I'd appreciate reproduction reports from other UNO Q / BMI088 setups, especially received topic rates and ideas for buffered sampling or acquisition timestamps. This is an independent hobby project, with no Bosch Sensortec affiliation or endorsement.

## Draft: Arduino Forum

**Title:** Project: BMI088 → ROS 2 Jazzy on UNO Q using App Lab and RouterBridge

I'm sharing my personal UNO Q project connecting a BMI088 IMU over the 3.3 V Qwiic bus (`Wire1`). The STM32 reads the sensor, RouterBridge transfers the measurements, and a custom Linux Brick publishes standard ROS 2 Jazzy IMU and temperature topics. The matrix also displays rounded sensor temperature.

The README includes wiring, one-line range/rate/filter configuration, and a listener. The supplied logs show roughly 65–68 received IMU messages/s with a 100 Hz target in one run.

I also documented a workaround for stale custom-Brick Python source after deployment: a read-only source mount and a small process supervisor. Image/dependency changes still need a rebuild; this is a project workaround, not an upstream App Lab fix.

https://github.com/mauringo/bosch-sensortec-ros2-unoq

If you try it, please share your BMI088 module, I²C addresses and received ROS rate. I'd also be interested in whether the source-reload workaround behaves consistently on other App Lab installations.

## Draft: short social post

BMI088 IMU → Arduino UNO Q → ROS 2 Jazzy.

My personal open-source example uses Arduino App Lab and RouterBridge to publish acceleration, angular velocity and sensor temperature. Includes wiring, a ROS listener and a custom-Brick source-reload workaround.

Observed in the supplied run: ~65–68 Hz received IMU data with a 100 Hz target. Next experiments: buffered sampling, acquisition timestamps and calibration.

Code and real output: https://github.com/mauringo/bosch-sensortec-ros2-unoq

I'd love to compare results with other UNO Q / BMI088 setups.
