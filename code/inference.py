import websocket
import uuid
import json
import urllib.request
import urllib.parse
import base64
from pydantic import BaseModel, Field
WORKING_DIR="/tmp/"

def write_gif_to_s3(gifs,output_s3uri=""):
    """
    write image to s3 bucket
    """
    s3_client = boto3.client('s3')
    bucket = os.environ.get("s3_bucket", "")
    prediction = []
    
    
    default_output_s3uri = f's3://{s3_bucket}/comfyui_output/images/'
    if output_s3uri is None or output_s3uri=="":
        output_s3uri=default_output_s3uri
    
    for node_id in images:
        for image_data in images[node_id]:
            from PIL import Image
            import io
            GIF_LOCATION = "{}/Comfyui_{}.gif".format(WORKING_DIR, node_id)
            print(GIF_LOCATION)
            with open(GIF_LOCATION, "wb") as binary_file:
                # Write bytes to file
                binary_file.write(image_data)
            s3_client.upload_file(
                Filename=GIF_LOCATION, 
                Bucket=bucket,
                Key=key
            )
            print('image: ', f's3://{bucket}/{key}')
            prediction.append(f's3://{bucket}/{key}')
    return prediction

def write_imgage_to_s3(images,output_s3uri=""):
    """
    write image to s3 bucket
    """
    s3_client = boto3.client('s3')
    bucket = os.environ.get("s3_bucket", "")
    prediction = []

    default_output_s3uri = f's3://{s3_bucket}/comfyui_output/images/'
    if output_s3uri is None or output_s3uri=="":
        output_s3uri=default_output_s3uri
    
    for node_id in images:
        for image_data in images[node_id]:
            image = Image.open(io.BytesIO(image_data))
            bucket, key = get_bucket_and_key(output_s3uri)
            key = f'{key}{uuid.uuid4()}.jpg'
            buf = io.BytesIO()
            image.save(buf, format='JPEG')
            s3_client.put_object(
                Body=buf.getvalue(),
                Bucket=bucket,
                Key=key,
                ContentType='image/jpeg',
                Metadata={
                    "seed": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            )
            print('image: ', f's3://{bucket}/{key}')
            prediction.append(f's3://{bucket}/{key}')
    return prediction

class InferenceOpt(BaseModel):
    prompt: str = "a photo of an astronaut riding a horse on mars"
    negative_prompt: str = ""
    steps: int = 20
    inference_type: str = "txt2img"

server_address = "localhost:8188"
client_id = str(uuid.uuid4())

def queue_prompt(prompt):
    print(prompt)
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    url = "http://"+server_address+"/prompt"
    req = urllib.request.Request(url, data=data)
    #req =  urllib.request.Request("http://ec2-34-222-223-235.us-west-2.compute.amazonaws.com:8188/prompt", data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_image_privew(filename):
    url = "http://{}/view?filename={}&type=output".format(server_address,filename)
    with urllib.request.urlopen(url) as response:
        return response.read()

def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen("http://{}/view?{}".format(server_address, url_values)) as response:
        return response.read()

def get_history(prompt_id):
    with urllib.request.urlopen("http://{}/history/{}".format(server_address, prompt_id)) as response:
        return json.loads(response.read())

def get_images(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    print("prompt_id=="+prompt_id)
    output_images = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break #Execution is done
        else:
            continue #previews are binary data

    history = get_history(prompt_id)[prompt_id]
    for o in history['outputs']:
        print("output==")
        print(o)
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                images_output = []
                for image in node_output['images']:
                    image_data = get_image(image['filename'], image['subfolder'], image['type'])
                    #image_data = get_image_privew(image['filename'])
                    print("image data==\n")
                    #image_text = (image_data).decode('utf-8') 
                    print(image_data)
                    images_output.append(image_data)
                output_images[node_id] = images_output
            # video branch
            if 'gifs' in node_output:
                videos_output = []
                for video in node_output['gifs']:
                    video_data = get_image(video['filename'], video['subfolder'], video['type'])
                    videos_output.append(video_data)
                output_images[node_id] = videos_output

    return output_images

def predict_fn(opt:InferenceOpt):
    try:
        prompt = json.loads(InferenceOpt.prompt_text)
        if InferenceOpt.inference_type == "text2img":
            ws = websocket.WebSocket()
            ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
            images = get_images(ws, prompt)
            prediction=write_imgage_to_s3(images)
        else if InferenceOpt.inference_type == "text2vid":
            ws = websocket.WebSocket()
            ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
            start_dt=time.time()
            images = get_images(ws, prompt)
            end_dt=time.time()
            print("time elapse:{:.6f} seconds".format(end_dt-start_dt))
            
            for node_id in images:
                for image_data in images[node_id]:
                    from PIL import Image
                    import io
                    GIF_LOCATION = "{}/Comfyui_{}.gif".format(WORKING_DIR, node_id)
                    print(GIF_LOCATION)
                    with open(GIF_LOCATION, "wb") as binary_file:
                        # Write bytes to file
                        binary_file.write(image_data)
    except Exception as ex:
        traceback.print_exc(file=sys.stdout)
        print(f"=================Exception=================\n{ex}")

    print('prediction: ', prediction)
    return prediction