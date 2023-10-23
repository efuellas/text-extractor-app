import boto3
import requests
from botocore.exceptions import NoCredentialsError
import streamlit as st


# AWS S3 Configuration
AWS_BUCKET_NAME = "billing-statement-textract"
AWS_REGION = "ap-southeast-1"

s3 = boto3.client('s3', region_name=AWS_REGION)

# Function to upload and save file to S3
def upload_file_to_s3(file, bucket_name, region):
    #s3 = boto3.client('s3', region_name=region)
    try:
        s3.upload_fileobj(file, bucket_name, "uploaded_file/" + file.name)
        return True
    except NoCredentialsError:
        st.error("AWS credentials not available.")
        return False
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        return False
    

def call_text_extract_api(bucket, key):

    api_url = 'https://h3oxjsbhn0.execute-api.ap-southeast-1.amazonaws.com/dev/extract-text'

    # Make a POST request to the API
    response = requests.post(
        api_url,
        headers={
            'Content-Type': 'application/json'
        },
        json={'bucket':bucket,
              'key': key}
    )

    # Parse and return the response
    data = response.json()
    #answer = data['choices'][0]['message']['content']
    return data

st.write("""# Text Extractor Application""")
st.write("""This application extracts the personal details from an ID photo.""")
st.write("""---""")
# Streamlit Upload Widget
file = st.file_uploader("Process ID", type=["jpg", "png", "jpeg"])

if file is not None:
    if st.button("Process ID"):
        if upload_file_to_s3(file, AWS_BUCKET_NAME, AWS_REGION):
            st.success(f"File '{file.name}' is being processed.")

            input_bucket = AWS_BUCKET_NAME 
            input_key = "uploaded_file/{}".format(file.name)

            try:
                file_obj = s3.get_object(Bucket=input_bucket, Key=input_key)
                file_extension = input_key.split('.')[-1].lower()
                
                if file_extension in ["jpg", "jpeg", "png"]:
                    st.write("### Image Viewer")
                    col1, col2, col3 = st.columns([1,6,1])
                    with col1:
                        st.write(' ')
                    with col2:
                        st.image(file_obj["Body"].read(), use_column_width=False, width=500)
                    with col3:
                        st.write(' ')

                    
                    response = call_text_extract_api(input_bucket, input_key)
                    st.write("""### Extracted text""")
                    st.write(response['result'])
                
                else:
                    st.error("Unsupported file type. Only images (jpg, png, jpeg) are supported.")

            except NoCredentialsError:
                st.error("AWS credentials not available.")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")

        else:
            st.error(f"File '{file.name}' was not processed.")