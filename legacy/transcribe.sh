#!/bin/bash

if [ -f ./trancribe.cfg ]
	then
		source "./trancribe.cfg"
	else
		echo "no config found. please run setup.sh first."
		exit 0
fi


export LC_NUMERIC="en_US.UTF-8"

trap ctrl_c INT

function ctrl_c() {
	echo "------------------------------"
	echo "STOPPING..."
	echo "bye bye"
	echo "------------------------------"
	exit
}

echo "Starting engines! Let's transcribe some episodes"
pushd whisper.cpp || exit

#------------------------------------------------------------------------------------
# get data for one episode to transcribe from matrix youtube
#------------------------------------------------------------------------------------

echo "getting data from youtube"
mkdir -p ./playlist
touch ./playlist/downloaded.txt
mkdir -p ./playlist_normalized
pushd ./playlist || exit

#PLAYLIST_URL="https://www.youtube.com/playlist?list=PLl5dnxRMP1hXBHqokHol6DTVIbnsf57Mr"
#PLAYLIST_URL="https://www.youtube.com/watch?v=HlsMMzTFZ_A"
PLAYLIST_URL="https://www.youtube.com/@Matrixdotorg"

python3 -m yt_dlp "${PLAYLIST_URL}" -x -f ba --audio-format wav --audio-quality 0 -o "%(id)s.%(ext)s" --concurrent-fragments 3 --download-archive ./downloaded.txt --live-from-start --extractor-args youtube:player_client=android
popd || exit

# exit if nothing to do

if [ -z "$(find "./playlist/" -maxdepth 1 -type f 2>/dev/null)" ];
	then
		echo "nothing to transcribe. exit!"
		exit 0;
fi

files_array=(./playlist/*.wav)
for next_file in "${files_array[@]}"
do
    FILENAME=$(basename "${next_file}" ".wav")

    # Skip file if output exists
    if [ -f "./output/${FILENAME}.vtt" ] || [ -f "./output/${FILENAME}.txt" ]; then
        rm "${next_file}"
    fi
done

echo "normalize"
files_already_done=($(find . -wholename "./playlist_normalized/*.wav" -type f | tr '\n' ' ' | sed -e 's/playlist_normalized/playlist/g'))
files=$(find . -wholename "./playlist/*.wav" -type f | tr '\n' ' ')
for already_done_file in "${files_already_done[@]}"
do
    files=$(echo "${files}" | sed -e "s@${already_done_file}@@g")
done
files_out=$(echo "${files}" | sed -e 's/playlist/playlist_normalized/g')

[[ $files = *[!\ ]* ]] && python3 -m ffmpeg_normalize ${files} -p -o ${files_out} -ar 16000

## This logic is used to not process stuff twice
#files_already_done=($(find . -wholename "./output/*.vtt" -type f | tr '\n' ' ' | sed -e 's/output/playlist_normalized/g' | sed -e 's/vtt/wav/g'))
files_already_done=($(find . -wholename "./output/*.txt" -type f | tr '\n' ' ' | sed -e 's/output/playlist_normalized/g'| sed -e 's/txt/wav/g'))
files=$(find . -wholename "./playlist_normalized/*.wav" -type f | tr '\n' ' ')
for already_done_file in "${files_already_done[@]}"
do
    files=$(echo "${files}" | sed -e "s@${already_done_file}@@g")
done
out_files=($(echo "${files}" | sed -e 's/playlist_normalized/output/g' | sed -e 's/.wav//g'))

echo "starting whisper"

if [[ $files = *[!\ ]* ]]; then
    array_files=(in cafiles)
    for i in "${!array_files[@]}"; do
	    echo "Starting with ${array_files[$1]}"
        #if ! nice -n 18 ./main -m "models/ggml-${MODEL}.bin" -t "$THREADS" -l en -ovtt -pc "${files}.wav"; #>/dev/null  2>/dev/null;
        if ! nice -n 18 ./main -m "models/ggml-${MODEL}.bin" -t "$THREADS" -l en -otxt -ovtt -pc --file "${array_files[$i]}" --output-file "${out_files[$i]}" -et 3.0; #>/dev/null  2>/dev/null;
            then
                echo "error transcribing"
        fi

        echo "cleanup"
        files_array=(./playlist_normalized/*.wav)
        for next_file in "${files_array[@]}"
        do
            FILENAME=$(basename "${next_file}" ".wav")
            # Removes some junk from hallucination
            sed -i -e 's/ Subtitles by the Amara.org community//g' "./output/${FILENAME}.txt"
            sed -i -e 's/Subtitles by the Amara.org community//g' "./output/${FILENAME}.vtt"

	        mkdir ./playlist_bak
	        mkdir ./playlist_normalized_bak
            mv "./playlist/${FILENAME}.wav" "./playlist_bak/${FILENAME}.wav"
            mv "./playlist_normalized/${FILENAME}.wav" "./playlist_normalized_bak/${FILENAME}.wav"
            #rm "./${FILENAME}.vtt"
            mv "./${FILENAME}.wav.vtt" "./output/${FILENAME}.vtt"
            mv "./${FILENAME}.wav.txt" "./output/${FILENAME}.txt"
        done
    done
fi

popd || exit
