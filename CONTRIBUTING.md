# Help improve the project

Thanks for trying it! Reproduction reports, clearer instructions and focused fixes are welcome. This is an independent personal project; support and new sensor integrations depend on available time and hardware.

## Share your results or report a problem

[Open an issue](https://github.com/mauringo/bosch-sensortec-ros2-unoq/issues) and include:

- Your BMI088 module (product link if possible), I²C addresses and wiring description.
- Arduino App Lab version and UNO Q software/firmware versions, if known.
- The sketch's `IMU` configuration line.
- What you expected, what happened and steps to reproduce it.
- Relevant Python and ROS logs, including received Hz and Bridge warnings.

Remove credentials and other private information from logs before sharing. Label sample output and simulations so they are not mistaken for measurements from a board.

For a new sensor, use the [sensor request form](https://github.com/mauringo/bosch-sensortec-ros2-unoq/issues/new?template=sensor-request.yml). Mention whether you have hardware available to test.

## Submit a change

Keep each pull request focused and describe the resulting behavior. For documentation changes, check links and commands. For runtime changes, run the existing simulated checks with Python and `msgpack` installed:

```bash
python3 -m unittest discover -s tests -v
```

These tests do not replace compilation or checks on an UNO Q. State which hardware checks you performed, or say that hardware was unavailable. See the [technical guide](docs/technical-guide.md) for protocol and deployment details.
