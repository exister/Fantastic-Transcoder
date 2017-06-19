# Fantastic Transcoder

Fantastic transcoder is a video transcoder which utilizes massively parallel compute to achieve ludicrous conversion speeds.

This is an orchestrated collection of Lambda tasks. We use DynamoDB, SQS, and S3 for data structure, job tracking, and object storage respectively.

The steps are as follows:

## Lambda 0: Poll
Runs every minute (triggered by cloudwatch cron)
- Polls SQS Queue ft_videoconvert_queue
- If a job is found, check to see if we've been here before with this ConversionID DynamoDB.FT_VideoConversions
- If ConversionID is not present, write to DynamoDB.FT_VideoConversions (ConversionID, created)
- If ConversionID is present, increment retry
- If retry count > some number, hard fail - Move to deadletter queue - Alert
- Update SQS Status Queue with status of "Waiting for encoder"

## Lambda 1: Segment
Triggered by DynamoDB.FT_VideoConversions
- Update SQS Status Queue with status of "Downloading"
- Grabs video from S3
- Update SQS Status Queue with status of "Ready to process"
- POSSIBLY Break out audio?? see TODO
- Segment Video
- Upload each segment to s3.VideoConversionsNG/Segmented/ConversionID/
- Log number of segments to DynamoDB.VideoConversions
- Write relevant data to DynamoDB.FT_SegmentState (ConversionID, SegmentID, created, ConversionFormat.each)
- Update SQS Status Queue with status of "Processing"

## Lambda 2: Transcode
Triggered by DynamoDB.FT_SegmentState
- If multiple formats are required, one row should be written per segment per ConversionFormat
- Downloads Video
- Runs ffprobe / greps for the correct max rectangle value to check dimensions of video
- Converts video to mp4 / dimensions depending on settings in convert.py
- Transcodes video to transport stream
- Uploads video to s3.VideoConversions/ConvertedSegments/ConversionID/Format{1,2,3}/
- Updates dynamoDB.FT_SegmentState with (ConversionID, SegmentID, created, complete, ConversionFormat.each)
- Checks if each Segment has been converted
- if all segments have been converted, trigger concat step by writing to DynamoDB.FT_VideoConversions

## Lambda 3: Concatenate
Triggered by DynamoDB.FT_VideoConversions.SegmentsComplete?
- Update SQS Status Queue with status of "Saving"
- One lambda triggered per format
- Downloads all converted transcode streams from s3.VideoConversions/ConvertedSegments/ConversionID/Format{1,2,3}/
- Makes sure all files are unique
- Checks DynamoDB to ensure it has the right / right number of segments. If not, Retry download
- Concatenates all segments into a single file
- Downloads and munges audio if we broke it out earlier?
- Places final transcoded file into s3 bucket
- Deletes message from SQS queue
- writes to DynamoDB.FT_VideoConversions.Complete
- Update SQS Status Queue with status of "Finished"

## DynamoDB Data structure
There are three tables within DynamoDB. ConversionID is the shared key between the tables. It's a unique identifier for each individual video to be converted.
- FT_VideoConversions triggers Conversions and contains basic data about the video file, such as the unique identifier and the number of retries.
- FT_ConversionState tracks state data about the overall conversion process.
- FT_SegmentState tracks the conversion status of each segment


## Failure Cases:
Any lambda, if ffmpeg exits with status other than 1, trigger failed in dynamoDB & update SQS queue message visibility to 1

## TODO for mvp
- get vweb up and dumping to correct bucket
- add sqs integration for first and last step (currently triggers from bucket)
- dynamoDB reads/writes added to individual functions
- Concat step functional testing & triggering off of dynamoDB.
- encoding parameters logic - decide how much is necessary. 3 formats?
- add SQS access to IAM role in terraform
- speak with legal about apache license

## TODO after mvp
- set up expiration time on s3 buckets
- developer documentation that includes how to alter the ffmpeg commands
- decide if we want to break out audio during segment and recombine during concatsn s3 buckets
- update bundler script, build full tutorial on how to integrate FC
- add support for converting audio files?
- add support for status queue:
    - MEDIASTATUS_NEW         = "New"
    - MEDIASTATUS_WAITING     = "Waiting for encoder"
    - MEDIASTATUS_DOWNLOADING = "Downloading"
    - MEDIASTATUS_READY       = "Ready to process"
    - MEDIASTATUS_PROCESSING  = "Processing"
    - MEDIASTATUS_SAVING      = "Saving"
    - MEDIASTATUS_FINISHED    = "Finished"
    - MEDIASTATUS_ERROR       = "Error"