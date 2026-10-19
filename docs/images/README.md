# Documentation images

These figures support the [project README](../../README.md) and [hardware guide](../hardware.md). The originals are kept in [originals/](originals/) with [SHA-256 checksums](originals/sha256.json).

| Figure | Published image | Unchanged original |
| --- | --- | --- |
| Cover — current | [UNO Q + BMI088 cover](uno-q-bmi088-cover.png) | AI-generated composite; see provenance below |
| 01 — earlier project preview | [Arduino UNO Q prototype](uno-q-bmi088-project-preview-enhanced.png) | [Original prototype photo](originals/project-preview-original.jpeg) |
| 02 — my hardware | [BMI088 shuttle board and adapter](bmi088-shuttle-board-adapter-enhanced.png) | [Original adapter photo](originals/bmi088-adapter-original.png) |
| 03 — where to click | [App Lab board-shell button](app-lab-open-board-shell.png) | [Original App Lab screenshot](originals/app-lab-console-original.png) |
| 04 — actual outcome | [ROS listener result](ros2-bmi088-listener-results.png) | [Original ROS log screenshot](originals/ros-listener-original.png) |

## What was improved

The README uses the selected 4:3 cover; the hardware guide retains the AI-enhanced adapter photograph with its original linked alongside it. The earlier faithful cropped JPEG versions remain available: [prototype crop](uno-q-bmi088-project-preview.jpg) and [adapter crop](bmi088-shuttle-board-adapter.jpg).

The screenshots retain their original resolution and measured text. The ROS log screenshot is placed unchanged inside a labeled frame. The App Lab screenshot has a callout on the board-shell button; measurement text is untouched. The captions and callout are documentation annotations, not App Lab interface elements.

The enhanced hardware image is an illustrative overview, not a wiring diagram. AI enhancement can change lettering, components or screen characters. Use the linked original photograph and manufacturer documentation for technical details.

## AI enhancement and source provenance

The two photographic illustrations were created with the built-in imagegen tool from the supplied photos and selected by the author for the README. The [prompt record](retouching-prompts.json) documents their generation. They are clearly labeled as AI-enhanced, and the original photographs remain linked alongside them. The ROS and App Lab screenshots are not AI-generated or AI-retouched.

The ROS screenshot supports approximately 65–68 Hz in the shown run. It is not a controlled benchmark or proof that the 100 Hz target was reached.

## Current cover

[uno-q-bmi088-cover.png](uno-q-bmi088-cover.png) is the selected `arduino-project-cover-v8.png`, copied unchanged at 1448 × 1086 pixels. It was created with the built-in imagegen tool using the author's prototype/device photos and supplied UNO Q and blue Grove BMI088 module references, followed by edits to connectors, the LED symbol and cable colors.

It is illustrative cover art, not an exact hardware photograph, pinout or recorded ROS output. Tiny components and markings may differ. The cover shows an Arduino symbol on the matrix, whereas the current sketch displays rounded temperature. The depicted Grove module is an untested alternative; the measured setup uses the shuttle board and adapter. Wire colors were edited for the cover and must not be used to infer pin assignments.

The earlier cover drafts in the project root are not used by the README. Keep technical claims tied to the original photos, manufacturer documentation and unaltered measurement screenshot.
