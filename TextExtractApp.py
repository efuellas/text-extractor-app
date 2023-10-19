import os
import boto3
import streamlit as st
from botocore.exceptions import NoCredentialsError
import requests
import base64
import json

# AWS S3 Configuration
AWS_BUCKET_NAME = st.secrets['AWS_BUCKET_NAME']
AWS_REGION = st.secrets['AWS_REGION']
OPENAI_API_KEY = st.secrets['OPENAI_API_KEY']

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

def documentTextDetect(input_bucket, input_key, output_bucket=None):

    # Initialize the Textract and S3 clients
    textract = boto3.client('textract')
    #s3 = boto3.client('s3')

    output_key = 'output/' + os.path.splitext(os.path.basename(input_key))[0] + '.txt'

    # Use Textract to extract text from the PDF document
    response = textract.start_document_text_detection(
        DocumentLocation={'S3Object': {'Bucket': input_bucket, 'Name': input_key}}
    )
    
    # Get the JobId from the Textract response
    job_id = response['JobId']

    # Wait for Textract job to complete
    while True:
        job_status = textract.get_document_text_detection(JobId=job_id)
        status = job_status['JobStatus']
        if status in ['SUCCEEDED', 'FAILED']:
            break

    if status == 'SUCCEEDED':
        # Extract and concatenate the detected text
        detected_text = ''
        for item in job_status['Blocks']:
            if item['BlockType'] == 'LINE':
                detected_text += item['Text'] + '\n'

        # Upload the detected text to the output S3 bucket
        # s3.put_object(Bucket=output_bucket, Key=output_key, Body=detected_text)

        return {
            'statusCode': 200,
            'body': 'Text extraction and save to S3 completed successfully.',
            'result': detected_text
        }
    else:
        return {
            'statusCode': 500,
            'body': 'Text extraction failed.'
        }


def chat_with_gpt(prompt, api_key, max_tokens=50):
    # The URL for the ChatGPT API endpoint
    api_url = 'https://api.openai.com/v1/chat/completions'

    # Make a POST request to the API
    response = requests.post(
        api_url,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        },
        json={
            'model': 'gpt-3.5-turbo',  # Use the turbo model for faster response
            'messages': [{'role': 'system', 'content': 'You are a helpful assistant.'},
                         {'role': 'user', 'content': prompt}],
            'max_tokens': max_tokens
        }
    )

    # Parse and return the response
    data = response.json()
    answer = data['choices'][0]['message']['content']
    return answer
   
st.write("""# Text Extractor Application""")
st.write("""This application extracts the personal details from an ID photo or a billing statement PDF file.""")
st.write("""---""")
# Streamlit Upload Widget
file = st.file_uploader("Upload a file", type=["pdf", "jpg", "png", "jpeg"])

if file is not None:
    if st.button("Upload to S3"):
        if upload_file_to_s3(file, AWS_BUCKET_NAME, AWS_REGION):
            st.success(f"File '{file.name}' has been uploaded to S3.")

            input_bucket = AWS_BUCKET_NAME 
            input_key = "uploaded_file/{}".format(file.name)
            output_bucket = AWS_BUCKET_NAME

            try:
                file_obj = s3.get_object(Bucket=input_bucket, Key=input_key)
                file_extension = input_key.split('.')[-1].lower()

                if file_extension in ["jpg", "jpeg", "png"]:
                    st.write("### Image Viewer")
                    st.image(file_obj["Body"].read(),  use_column_width=True)
                elif file_extension == "pdf":
                    st.write("### PDF Viewer")
                    #st.write(file_obj["Body"].read())

                    # with open(file_obj["Body"].read(),"rb") as f:
                    base64_pdf = base64.b64encode(file_obj["Body"].read()).decode('utf-8')

                    pdf_display = F'<embed src="data:application/pdf;base64,{base64_pdf}" width="700" height="850" type="application/pdf">'

                    st.markdown(pdf_display, unsafe_allow_html=True)
                else:
                    st.error("Unsupported file type. Only images (jpg, png, jpeg) and PDFs are supported.")
            except NoCredentialsError:
                st.error("AWS credentials not available.")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")

            response = documentTextDetect(input_bucket, input_key)

            if '.pdf' in file.name:
                prompt = """{}

                    From the text above, answer the following questions:
                    1. What is the name of the Company?
                    2. What is the Account Number of the Customer?
                    3. What is the name of the Customer?
                    4. What is the address of the Customer?

                    Follow the format below. No sentences.
                    1. Billing Company: 
                    2. Customer Account Number:
                    3. Customer Name:
                    4. Customer Address:
                    """.format(response['result'])
                
                response = chat_with_gpt(prompt, OPENAI_API_KEY)

                st.write("""### Extracted text""")
                st.write("{}".format(response))

                # json_response = json.loads(response)

                # st.write("""*Company Name:* {}
                #          *Customer Account Number:* {}
                #          *Customer Name:* {}
                #          *Customer Address:* {}""".format(json_response['CompanyName'], json_response['CustomerAccountNumber'], 
                #                                           json_response['CustomerName'], json_response['CustomerAddress']))

            else:
                prompt = """{}

                    From the text above, answer the following questions:
                    1. What type of ID is submitted?
                    2. What is the name of the Customer?
                    3. What is the address of the Customer?

                    Follow the format below. No sentences.
                    1. ID:
                    2. Customer Name:
                    3. Customer Address:
                     
                    """.format(response['result'])
                
                response = chat_with_gpt(prompt, OPENAI_API_KEY)

                st.write("""### Extracted text""")
                st.write("{}".format(response))

                # json_response = json.loads(response)

                # st.write("""*Customer Name:* {}
                #          *Customer Address:* {}""".format(json_response['CustomerName'], json_response['CustomerAddress']))

        else:
            st.error(f"File '{file.name}' failed to upload to S3.")
