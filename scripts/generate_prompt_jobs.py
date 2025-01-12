import argparse
import sys
import io

base_directory = "./"
sys.path.insert(0, base_directory)

from stable_diffusion import CLIPTextEmbedder
from stable_diffusion.model_paths import (SDconfigs, CLIPconfigs)
from configs.model_config import ModelPathConfig
from worker.prompt_generation.prompt_generator import (initialize_prompt_list_from_csv)
from worker.prompt_generation.prompt_generator import generate_prompts_proportional_selection, generate_base_prompts, load_base_prompts
from utility.minio import cmd
from utility.path import separate_bucket_and_file_path
from training_worker.ab_ranking.model.ab_ranking_efficient_net import ABRankingEfficientNetModel
from training_worker.ab_ranking.model.ab_ranking_linear import ABRankingModel
from worker.prompt_generation.prompt_generator import (generate_inpainting_job,
                                                       generate_image_generation_jobs)

def generate_prompts(clip_text_embedder, dataset, scoring_model, prompt_count, csv_dataset_path, base_prompts_csv_path, top_k):

    total_prompt_count = prompt_count * (1.0 / top_k)

    total_prompt_count = int(total_prompt_count)

    phrases, phrases_token_size, positive_count_list, negative_count_list = initialize_prompt_list_from_csv(
        csv_dataset_path, 0)


    print(f'generating {total_prompt_count} prompts for dataset {dataset}')
    prompts = generate_prompts_proportional_selection(phrases,
                                                      phrases_token_size,
                                                      positive_count_list,
                                                      negative_count_list,
                                                      total_prompt_count,
                                                      '')

    base_prompt_population = load_base_prompts(base_prompts_csv_path)

    scored_prompts = []
    for prompt in prompts:

        # N Base Prompt Phrases
        # Hard coded probability of choose 0,1,2,3,4,5, etc base prompt phrases
        # Chance for 0 base prompt phrases should be 30%
        # choose_probability = [0.3, 0.3, 0.2, 0.2, 0.2]
        choose_probability = [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]

        base_prompt_list = generate_base_prompts(base_prompt_population, choose_probability)

        base_prompts = ''

        for base_prompt in base_prompt_list:
            base_prompts = base_prompts + base_prompt + ', '

        positive_text_prompt = base_prompts + prompt.positive_prompt_str
        negative_text_prompt = prompt.negative_prompt_str

        prompt_score = 0
        if scoring_model is not None and clip_text_embedder is not None:
            # get prompt embeddings
            positive_prompt_embeddings = clip_text_embedder(positive_text_prompt)
            negative_prompt_embeddings = clip_text_embedder(negative_text_prompt)

            prompt_score = scoring_model.predict(positive_prompt_embeddings,
                                                           negative_prompt_embeddings).item()

        scored_prompt = ScoredPrompt(prompt_score, positive_text_prompt, negative_text_prompt)
        scored_prompts.append(scored_prompt)

    # Sort the list based on the maximize_int1 function
    sorted_scored_prompts = sorted(scored_prompts, key=maximize_score)

    chosen_scored_prompts = sorted_scored_prompts[:prompt_count]

    return chosen_scored_prompts

class ScoredPrompt:
    def __init__(self, score, positive_prompt, negative_prompt):
        self.score = score
        self.positive_prompt = positive_prompt
        self.negative_prompt = negative_prompt


def maximize_score(scored_prompt):
    return -scored_prompt.score


def load_linear_model(minio_client, dataset_bucket, model_path):

    linear_model = ABRankingModel(768*2)

    model_file_data = cmd.get_file_from_minio(minio_client, dataset_bucket, model_path)

    if model_file_data is None:
        return

    # Create a BytesIO object and write the downloaded content into it
    byte_buffer = io.BytesIO()
    for data in model_file_data.stream(amt=8192):
        byte_buffer.write(data)
    # Reset the buffer's position to the beginning
    byte_buffer.seek(0)

    linear_model.load(byte_buffer)

    return linear_model


def generate_environmental_image_generation_jobs(scored_prompt):

    dataset_name = 'environmental'

    print(f"Adding '{dataset_name}' generation job")


    if scored_prompt is None:
        return

    positive_prompt = scored_prompt.positive_prompt
    negative_prompt = scored_prompt.negative_prompt

    generate_image_generation_jobs(
        positive_prompt=positive_prompt,
        negative_prompt=negative_prompt,
        dataset_name=dataset_name,
    )

def parse_args():
    parser = argparse.ArgumentParser(description="generate prompts")

    # Required parameters
    parser.add_argument("--device", type=str, default='cuda')
    parser.add_argument("--dataset", type=str, default='environmental')
    parser.add_argument("--top_k", type=float, default=0.1)
    parser.add_argument("--prompt_count", type=int, default=1)
    parser.add_argument("--csv_dataset_path", type=str, default='input/civitai_phrases_database_v6.csv')
    parser.add_argument("--csv_base_prompts", type=str,
                        default='input/dataset-config/environmental/base-prompts-environmental.csv')

    parser.add_argument("--model_path", type=str,
                        default='environmental/models/ranking/ab_ranking_linear/2023-10-13.pth')

    parser.add_argument("--minio_access_key", type=str, default='v048BpXpWrsVIHUfdAix')
    parser.add_argument("--minio_secret_key", type=str, default='4TFS20qkxVuX2HaC8ezAgG7GaDlVI1TqSPs0BKyu')

    return parser.parse_args()


def main():
    args = parse_args()

    device = args.device
    dataset = args.dataset
    csv_base_prompts = args.csv_base_prompts
    top_k = args.top_k
    csv_dataset_path = args.csv_dataset_path
    prompt_count = args.prompt_count
    minio_secret_key = args.minio_secret_key
    minio_access_key = args.minio_access_key
    model_path = args.model_path

    clip_text_embedder = CLIPTextEmbedder(device=device)
    config = ModelPathConfig()
    clip_text_embedder.load_submodels(
        tokenizer_path=config.get_model_folder_path(CLIPconfigs.TXT_EMB_TOKENIZER),
        transformer_path=config.get_model_folder_path(CLIPconfigs.TXT_EMB_TEXT_MODEL)
    )

    minio_client = cmd.get_minio_client(minio_access_key, minio_secret_key)

    bucket_name, file_path = separate_bucket_and_file_path(model_path)

    scoring_model = load_linear_model(minio_client, 'datasets', model_path)

    prompt_list = generate_prompts(clip_text_embedder, dataset, scoring_model, prompt_count, csv_dataset_path,
                         csv_base_prompts, top_k)

    for prompt in prompt_list:
        generate_environmental_image_generation_jobs(prompt)


if __name__ == '__main__':
    main()



