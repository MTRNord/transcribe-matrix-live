#!/usr/bin/env python3

import argparse
import logging
import os
import shutil
import signal
import subprocess
from pathlib import Path
from typing import Any, Dict, List

import librosa
import matplotlib
import matplotlib.pyplot as plt
import tqdm
import yt_dlp
from ffmpeg_normalize import FFmpegNormalize
from matplotlib import font_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Define constants
CONFIG_FILENAMES: List[str] = ["transcribe.cfg", "trancribe.cfg"]
DEFAULT_THREADS: int = 1
DEFAULT_MODEL: str = "medium"
DEFAULT_PLAYLIST_URL: str = "https://www.youtube.com/@Matrixdotorg"
SCRIPT_DIR: Path = Path(__file__).resolve().parent


# Define the function to handle Ctrl+C
def ctrl_c(sig: int, frame: Any) -> None:
    logging.info("------------------------------")
    logging.info("STOPPING...")
    logging.info("bye bye")
    logging.info("------------------------------")
    exit(0)


# Set the signal handler
signal.signal(signal.SIGINT, ctrl_c)


def load_configuration(config_filenames: List[str]) -> Dict[str, str]:
    config: Dict[str, str] = {}
    for filename in config_filenames:
        if Path(filename).is_file():
            with open(filename, "r") as cfg_file:
                for line in cfg_file:
                    if line.strip() and not line.startswith("#"):
                        key, value = line.strip().split("=")
                        config[key.strip()] = value.strip()
    return config


def create_config_file() -> None:
    threads: int = get_thread_count()
    model: str = (
        input("Enter the model (Press Enter for default): ").strip() or DEFAULT_MODEL
    )

    # Save configuration
    with open("transcribe.cfg", "w") as cfg_file:
        cfg_file.write(f"THREADS={threads}\n")
        cfg_file.write("PIDFILE=~/.trancribe-transcribe.pid\n")
        cfg_file.write(f"MODEL={model}\n")


def check_dependencies() -> None:
    dependencies: List[str] = ["ffmpeg", "git"]
    for dependency in dependencies:
        if shutil.which(dependency) is None:
            logging.error(f"Can't find {dependency}. Please install.")
            exit(1)


def setup_whisper() -> None:
    whisper_dir: Path = SCRIPT_DIR / "whisper.cpp"
    if not (whisper_dir / "whisper.cpp").exists():
        logging.info("Downloading whisper.cpp")
        subprocess.run(
            ["git", "clone", "https://github.com/ggerganov/whisper.cpp"],
            cwd=SCRIPT_DIR,
            check=True,
        )
        logging.info("Compiling whisper...")
        subprocess.run(["make", "-j", "WHISPER_CLBLAST=1"], cwd=whisper_dir, check=True)
        logging.info("Downloading the model")
        subprocess.run(
            ["./models/download-ggml-model.sh", "medium"], cwd=whisper_dir, check=True
        )
    else:
        os.chdir(whisper_dir)


def get_thread_count() -> int:
    threads: int = 0
    try:
        threads = os.cpu_count() or 0
    except Exception as e:
        logging.error(f"Error getting number of threads: {str(e)}")

    if threads == 0:
        logging.warn("Could not find the number of threads.")
    else:
        logging.info(f"Maximum of {threads} threads found.")

    input_threads: str = input(
        "How many threads to use for transcription? (Press Enter for default): "
    )

    if input_threads.strip():
        try:
            threads = int(input_threads)
        except ValueError:
            logging.error("Invalid input. Using default.")
    return threads


def run_transcription_test(config: Dict[str, str]) -> None:
    threads: int = int(config.get("THREADS", DEFAULT_THREADS))
    model: str = config.get("MODEL", DEFAULT_MODEL)

    logging.info("Starting test. This might take some minutes, please wait...")

    thread_opt: str = f"-t {threads}" if threads else ""

    try:
        subprocess.run(
            [
                "./main",
                "-m",
                f"models/ggml-{model}.bin",
                thread_opt,
                "-l",
                "de",
                "-di",
                "../test.wav",
            ],
            check=True,
        )
    except subprocess.CalledProcessError:
        logging.error("Error transcribing. Stopping.")


def download_audio_files(playlist_url: str, output_directory: str) -> None:
    # Download audio files from YouTube playlist
    ydl_opts: yt_dlp.YDLOpts = {
        "format": "bestaudio/best",
        "outtmpl": f"{output_directory}/%(id)s.%(ext)s",
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
        "concurrent_fragment_downloads": 3,
        "download_archive": f"{output_directory}/downloaded.txt",
        "live_from_start": True,
        "extractor_args": {"youtube": {"player_client": "android"}},
    }  # type: ignore

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([playlist_url])


def normalize_audio_files(input_directory: str, output_directory: str) -> None:
    # Normalize audio files using FFmpegNormalize
    files: List[str] = [
        file for file in os.listdir(input_directory) if file.endswith(".wav")
    ]

    # Filter out files that are already in the output directory
    existing_files = os.listdir(output_directory)
    files_to_normalize = [file for file in files if file not in existing_files]

    files_in: List[str] = [f"{input_directory}/{file}" for file in files_to_normalize]
    files_out: List[str] = [f"{output_directory}/{file}" for file in files_to_normalize]

    normalizer = FFmpegNormalize(
        progress=True,
        video_disable=True,
        sample_rate=16000,
    )
    for input_file, output_file in zip(files_in, files_out):
        normalizer.add_media_file(input_file, output_file)
    normalizer.run_normalization()


def generate_graph(audio_directory: str) -> None:
    logging.info("Generating graph over audio files")
    audio_files: List[str] = [
        file for file in os.listdir(audio_directory) if file.endswith(".wav")
    ]

    # Get lengths of audio files
    audio_lengths: List[float] = []
    progress_bar = tqdm.tqdm(total=len(audio_files), desc="Processing audio files")

    for file in audio_files:
        audio_path = os.path.join(audio_directory, file)
        duration = librosa.get_duration(path=audio_path)
        audio_lengths.append(duration)
        progress_bar.update(1)

    progress_bar.close()

    # Create histogram with specified bins
    plt.figure(figsize=(15, 8))
    counts, bins, bars = plt.hist(
        audio_lengths,
        bins=50,
        color="skyblue",
        rwidth=0.7,
    )

    plt.xlabel(
        "Audio Length",
        labelpad=15,
        color="#333333",
        fontname="Inter",
    )
    plt.ylabel(
        "Frequency",
        labelpad=15,
        color="#333333",
        fontname="Inter",
    )
    plt.title(
        "Distribution of Audio Lengths",
        pad=15,
        color="#333333",
        weight="bold",
        fontname="Inter",
    )

    # Format x-axis ticks for better readability
    formatter = matplotlib.ticker.FuncFormatter(  # type: ignore
        lambda x, _: "{:.0f}h {:.0f}m".format(x // 3600, (x % 3600) // 60)
    )
    plt.gca().xaxis.set_major_formatter(formatter)
    plt.gca().set_xticks(bins)
    plt.gca().set_xticklabels(plt.gca().get_xticklabels(), rotation=45, ha="right")
    plt.gca().spines["top"].set_visible(False)
    plt.gca().spines["right"].set_visible(False)
    plt.gca().spines["left"].set_visible(False)
    plt.gca().spines["bottom"].set_color("#DDDDDD")
    plt.gca().tick_params(bottom=True, left=False)
    plt.gca().set_axisbelow(True)
    plt.gca().yaxis.grid(True, color="#EEEEEE")
    plt.gca().xaxis.grid(False)

    plt.tight_layout()

    # Save the histogram as an image file
    plt.savefig("../audio_lengths_histogram.png")

    # Close the plot to release resources
    plt.close()


def transcribe_audio_files(files_directory: str, model: str, threads: int) -> None:
    files: List[str] = [
        file for file in os.listdir(files_directory) if file.endswith(".wav")
    ]

    for file in files:
        input_file: str = f"{files_directory}/{file}"
        base_filename: str = os.path.splitext(file)[0]
        output_file: str = f"output/{base_filename}"

        # Check if any of the output files already exist
        txt_exists = os.path.exists(f"output/{base_filename}.txt")
        srt_exists = os.path.exists(f"output/{base_filename}.srt")
        vtt_exists = os.path.exists(f"output/{base_filename}.vtt")
        if not (txt_exists and srt_exists and vtt_exists):
            whisper_cmd: List[str] = [
                "./main",
                "-m",
                f"models/ggml-{model}.bin",
                "-t",
                str(threads),
                "-l",
                "en",
                "-otxt",
                "-ovtt",
                "-osrt",
                "-pc",
                "--file",
                input_file,
                "--output-file",
                output_file,
                "-et",
                "3.0",
            ]

            whisper_process: subprocess.CompletedProcess = subprocess.run(
                whisper_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            if whisper_process.returncode != 0:
                logging.error("Error transcribing")
            else:
                logging.info("Transcription successful")


def backup_files(
    input_directory: str, normalized_directory: str, backup_directory: str
) -> None:
    # Backup input files
    input_files: List[str] = [
        file for file in os.listdir(input_directory) if file.endswith(".wav")
    ]
    for file in input_files:
        input_file: str = f"{input_directory}/{file}"
        shutil.move(input_file, f"{backup_directory}/input/{file}")
        logging.info(f"Moved input file {file} to backup directory")

    # Backup normalized input files
    normalized_files: List[str] = [
        file for file in os.listdir(normalized_directory) if file.endswith(".wav")
    ]
    for file in normalized_files:
        normalized_file: str = f"{normalized_directory}/{file}"
        shutil.move(normalized_file, f"{backup_directory}/normalized/{file}")
        logging.info(f"Moved normalized file {file} to backup directory")


def run() -> None:
    # Load configuration
    config: Dict[str, str] = load_configuration(CONFIG_FILENAMES)
    threads: int = int(config.get("THREADS", DEFAULT_THREADS))
    model: str = config.get("MODEL", DEFAULT_MODEL)
    playlist_url: str = config.get("PLAYLIST_URL", DEFAULT_PLAYLIST_URL)

    # Set LC_NUMERIC
    os.environ["LC_NUMERIC"] = "en_US.UTF-8"

    logging.info("Starting engines! Let's transcribe some episodes")

    # Change directory to whisper.cpp
    os.chdir("whisper.cpp")

    # Create necessary directories if they don't exist
    os.makedirs("./playlist", exist_ok=True)
    open("./playlist/downloaded.txt", "a").close()
    os.makedirs("./playlist_normalized", exist_ok=True)

    download_audio_files(playlist_url, "./playlist")

    generate_graph("./playlist")

    # Normalize audio files
    normalize_audio_files("./playlist", "./playlist_normalized")

    # Transcribe audio files
    transcribe_audio_files("./playlist_normalized", model, threads)

    # Cleanup
    backup_files("./playlist", "./output", "./backup")

    logging.info("Transcription completed!")

    # Change back to the original directory
    os.chdir("..")


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Transcription script"
    )
    parser.add_argument("--setup", help="Mode of operation")
    args: argparse.Namespace = parser.parse_args()

    if args.setup:
        create_config_file()
        config: Dict[str, str] = load_configuration(CONFIG_FILENAMES)
        check_dependencies()
        setup_whisper()
        run_transcription_test(config)
    else:
        run()


if __name__ == "__main__":
    main()
