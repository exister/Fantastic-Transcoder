import boto3
import ffmpy
import os

s3 = boto3.resource('s3')
s3_client = boto3.client('s3')

def lambda_handler(event, context):

    # Get the object from the event and show its content type
    global bucket
    bucket = event['Records'][0]['s3']['bucket']['name']
    global key
    key = event['Records'][0]['s3']['object']['key']

    print "key is {}".format(key)
    print "bucket is {}".format(bucket)

    if not key.endswith('/'):
        try:
            # Finagle S3 bucket naming conventions so that boto retrieves the correct file
            global split_key
            split_key = key.split('/')
            global file_name
            file_name = split_key[-1]
            global file_extension
            file_extension = os.path.splitext(file_name)[1]
            print "segmenting {} file".format(file_extension)
            # Download the source file from s3
            s3_client.download_file(bucket, key, '/tmp/'+file_name)

            # Call ffmpy function
            perform()

            global destination


            # Each chunk is uploaded to s3
            print "Uploading segments to s3..."
            for filename in os.listdir('/tmp/SEGMENT*'):
                destination = 'Segmented/{}'.format(filename)
                s3_client.upload_file('/tmp/'+filename, bucket, destination)
        except Exception as e:
            print(e)
            print('ERROR! Key: {} Bucket: {}. Make sure they exist and your bucket is in the same region as this function.'.format(key, bucket))
            raise e


# ffmpy invocation that SEGMENTs the video into chunks
def perform():
    if key is not None:
        ff = ffmpy.FFmpeg(
        executable='./ffmpeg/ffmpeg',
        inputs={'/tmp/'+file_name : None},
        outputs={'/tmp/SEGMENT%d{}'.format(file_extension): '-acodec copy -c:a libfdk_aac -f segment -vcodec copy -reset_timestamps 1 -map 0'}
        )
        ff.run()
