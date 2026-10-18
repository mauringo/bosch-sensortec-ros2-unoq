# Documentation images

These four figures belong to the [project README](../../README.md). The originals are kept in [originals/](originals/) with [SHA-256 checksums](originals/sha256.json).

| Figure | Published image | Unchanged original |
| --- | --- | --- |
| 01 — project preview | [Arduino UNO Q prototype](uno-q-bmi088-project-preview.jpg) | [Original prototype photo](originals/project-preview-original.jpeg) |
| 02 — my hardware | [BMI088 shuttle board and adapter](bmi088-shuttle-board-adapter.jpg) | [Original adapter photo](originals/bmi088-adapter-original.png) |
| 03 — where to click | [App Lab board-shell button](app-lab-open-board-shell.png) | [Original App Lab screenshot](originals/app-lab-console-original.png) |
| 04 — actual outcome | [ROS listener result](ros2-bmi088-listener-results.png) | [Original ROS log screenshot](originals/ros-listener-original.png) |

## What was improved

The photographs were cropped to remove empty space, lightly adjusted for exposure/contrast, resized and saved as optimized JPEGs. The frames use consistent titles and captions.

The screenshots retain their original resolution and measured text. The ROS log screenshot is placed unchanged inside a labeled frame. The App Lab screenshot has a callout on the board-shell button; measurement text is untouched. The captions and callout are documentation annotations, not App Lab interface elements.

The hardware photo is for identification. It is not a wiring diagram, and its original focus limits how much silkscreen detail can be recovered.

## AI-retouching check

Two photographic retouching drafts were evaluated with the built-in imagegen tool. They were not used in the published figures because they changed technical lettering or screen characters. The [prompt record](retouching-prompts.json) documents that attempt. All published photographs and screenshots come from the supplied originals.

The ROS screenshot supports approximately 65–68 Hz in the shown run. It is not a controlled benchmark or proof that the 100 Hz target was reached.
