
import sys
import time
import requests

base_directory = "./"
sys.path.insert(0, base_directory)

from generation_task.icon_generation_task import IconGenerationTask
from generation_task.image_generation_task import ImageGenerationTask

from worker.image_generation.scripts.generate_images_with_inpainting_from_prompt_list import run_generate_images_with_inpainting_from_prompt_list



SERVER_ADRESS = 'http://127.0.0.1:8000'

# Running inpainting using the inpainting script
# TODO(): each generation task should have its own function
def run_generation_task(generation_task):

    # Instead of using cli arguments, we are using the
    # Generation_task class to provide the parameters
    args = {
        'prompt_list_dataset_path' : generation_task.prompt_list_dataset_path,
        'num_images' : generation_task.num_images,
        'init_img': generation_task.init_img,
        'init_mask': generation_task.init_mask,
        'sampler_name': generation_task.sampler,
        'batch_size': 1,
        'n_iter': generation_task.num_images,
        'steps': generation_task.steps,
        'cfg_scale': generation_task.cfg_strength,
        'width': generation_task.width,
        'height': generation_task.height,
        'outpath': generation_task.output_path

    }
    run_generate_images_with_inpainting_from_prompt_list(args)

# Get request to get an available job
def http_get_job():
    url = SERVER_ADRESS + "/get-job"
    job = requests.get(url)
    job_json = job.json()

    return job_json

# Used for debugging purpose
# The worker should not be adding jobs
def http_add_job(job):
    url = SERVER_ADRESS + "/get-list-pending-jobs"
    headers = {"Content-type": "application/json"}  # Setting content type header to indicate sending JSON data
    response = requests.post(url, json=job, headers=headers)
    print("response ", response)
    if response.status_code != 201:
        print(f"POST request failed with status code: {response.status_code}")

def main():
    print("starting")

    # for debugging purpose only
    http_add_job({
        "uuid": 1,
        "task_type": "icon_generation_task",
        "task_creation_time": "ignore",
        "model_name" : "sd",
        "task_input_dict": {
            'prompt': "icon",
            'cfg_strength': 7.5,
            'iterations': 1,
            'denoiser': "",
            'seed': '',
            'output_path': "./output/inpainting/",
            'num_images': 6,
            'image_width': 512,
            'image_height': 512,
            'batch_size': 1,
            'checkpoint_path': 'input/model/sd/v1-5-pruned-emaonly/v1-5-pruned-emaonly.safetensors',
            'flash': False,
            'device': "cuda",
            'sampler': "ddim",
            'steps': 20,
            'prompt_list_dataset_path': './input/civit_ai_data_phrase_count_v6.csv',
            'init_img': './test/test_inpainting/white_512x512.jpg',
            'init_mask': './test/test_inpainting/icon_mask.png',
        },

        "task_input_file_dict": {},
        "task_output_file_dict": {},
    })


    while True:
        job = http_get_job()
        if job != None:
            # Convert the job entry into a dictionary
            # Then feed the dictionary into the generation task
            # Question : Do we want to keep converting the database entries to
            # Our own version of GenerationTask struct ?
            # Probably yes, since there will be many different types of
            # GenerationTask struct and they will have different fields
            task = {
                'generation_task_type' : job['task_type'],
                'prompt': job['task_input_dict']['prompt'],
                'model_name': job['model_name'],
                'cfg_strength': job['task_input_dict']['cfg_strength'],
                'iterations': job['task_input_dict']['iterations'],
                'denoiser': job['task_input_dict']['denoiser'],
                'seed': job['task_input_dict']['seed'],
                'output_path': job['task_input_dict']['output_path'],
                'image_width': job['task_input_dict']['image_width'],
                'image_height': job['task_input_dict']['image_height'],
                'batch_size': job['task_input_dict']['batch_size'],
                'checkpoint_path': job['task_input_dict']['checkpoint_path'],
                'flash': job['task_input_dict']['flash'],
                'device': job['task_input_dict']['device'],
                'sampler': job['task_input_dict']['sampler'],
                'steps': job['task_input_dict']['steps'],
                'prompt_list_dataset_path': job['task_input_dict']['prompt_list_dataset_path'],
                'init_img': job['task_input_dict']['init_img'],
                'init_mask': job['task_input_dict']['init_mask'],
            }

            # Switch on the task type
            # We have 2 for now
            # And they are identical
            task_type = task['generation_task_type']

            if task_type == 'icon_generation_task':
                generation_task = IconGenerationTask.from_dict(task)
                # Run inpainting task
                run_generation_task(generation_task)

            elif task_type == 'image_generation_task':
                generation_task = ImageGenerationTask.from_dict(task)
                # Run inpainting task
                run_generation_task(generation_task)

        else:
            # If there was no job, go to sleep for a while
            sleep_time_in_seconds = 1
            time.sleep(sleep_time_in_seconds * 1000)




if __name__ == '__main__':
    main()
