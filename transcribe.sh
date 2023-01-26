#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

if [ -f ./trancribe.cfg ]
	then
		source "./trancribe.cfg"
	else
		echo "no config found. please run setup.sh first."
		exit 0
fi


export LC_NUMERIC="en_US.UTF-8"

trap ctrl_c INT
trap stop EXIT

function stop {
	rm $PIDFILE
}

function ctrl_c() {
	
	echo "------------------------------"
	echo "STOPPING..."
	echo "bye bye"
	echo "------------------------------"
	rm -f $PIDFILE
	exit 
}

pid() {
	if [ -f $PIDFILE ]
	then
	  PID=$(cat $PIDFILE)
	  ps -p $PID > /dev/null 2>&1
	  if [ $? -eq 0 ]
	  then
		echo "Process already running"
		exit 1
	  else
		## Process not found assume not running
		echo $$ > $PIDFILE
		if [ $? -ne 0 ]
		then
		  echo "Could not create PID file"
		  exit 1
		fi
	  fi
	else
	  echo $$ > $PIDFILE
	  if [ $? -ne 0 ]
	  then
		echo "Could not create PID file"
		exit 1
	  fi
	fi
}

pid

echo "Starting engines! Let's transcribe some episodes"
pushd whisper.cpp

#------------------------------------------------------------------------------------
# get data for one episode to transcribe from matrix youtube
#------------------------------------------------------------------------------------

echo "getting data from youtube"
mkdir -p ./playlist
pushd ./playlist
yt-dlp "https://www.youtube.com/playlist?list=PLl5dnxRMP1hXBHqokHol6DTVIbnsf57Mr" -x --audio-format wav --audio-quality 0 -o "%(id)s.%(ext)s"
popd

while :
do
    
	# exit if nothing to do

	if ! [ -n "$(find "./playlist/" -maxdepth 1 -type f 2>/dev/null)" ];
		then
			echo "nothing to transcribe. exit!"
			exit 0;
	fi
	
	#------------------------------------------------------------------------------------
	# transcribe wav to vtt
	#------------------------------------------------------------------------------------

    files=(./playlist/*.wav)
    next_file="${files[0]}"
    echo "Working on \"${next_file}\" next"
    FILENAME=$(basename ${next_file})
    mv "${next_file}" ./${FILENAME}_orig

    ffmpeg -y -i ./${FILENAME}_orig -acodec pcm_s16le -ac 1 -ar 16000 ./${FILENAME} >/dev/null  2>/dev/null
    rm ./${FILENAME}_orig

    DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 ./${FILENAME} 2>&1)
    echo "start working on episode ${FILENAME}, duration $DURATION seconds"

	START=`date +%s`
	
	echo "starting whisper"
	nice -n 18 ./main -su -m models/ggml-$MODEL.bin -t $THREADS -l en -ovtt ./${FILENAME} >/dev/null  2>/dev/null
	
	if [ $? -ne 0 ]
		then
			echo "error transcribing"
			continue
		
	fi
	
	END=`date +%s`
	TOOK=$(($END-$START))

	echo -n "Rate: "
	printf "%.2f" $(echo "$DURATION/$TOOK" | bc -l)
	echo "x"

    rm ./${FILENAME}
	#rm ./${FILENAME}.vtt
    mkdir -p ./output
    mv ./${FILENAME}.vtt ./output/${FILENAME}.vtt
	
	if [ -f ~/.trancribe-stop ]; then
		rm ~/.trancribe-stop
		echo "stopping hard"
		exit
	fi

	echo "--------------------------------------------------------------"
	sleep 2
	
done

popd

rm $PIDFILE
