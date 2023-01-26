# transcribe
A fork for matrix-live transcription@home by fyyd.de 

This is not fully tested. You need a decent CPU. You also need these deps:

- ffmpeg
- git
- yt-dlp

Next you need to run `./setup.sh` this will ask how many cores you want to use and it will test the setup.
It also downloads and compiles the core of this: [whisper.cpp](https://github.com/ggerganov/whisper.cpp)

To start transcribing you can run `./transcribe.sh`.
You can cancel it with ctrl+c at any time. or create a `.trancribe-stop` file in the parent folder to stop after the current transcription.

You find the vtt outputs in the `./whisper.cpp/output/` folder.
The name contains the video id.
Youtube allows you to upload these:

- https://support.google.com/youtube/answer/2734796?hl=en#zippy=%2Cupload-a-file
- https://support.google.com/youtube/answer/2734698#zippy=%2Cadvanced-file-formats
