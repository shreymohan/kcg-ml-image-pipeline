from fastapi import Request, HTTPException, APIRouter, Response, Query
from datetime import datetime
from utility.minio import cmd
from utility.path import separate_bucket_and_file_path


router = APIRouter()


@router.get("/image/get_random_image")
def get_random_image(request: Request, dataset: str = Query(...)):  # Remove the size parameter
  
    # Use $sample to get one random document
    documents = request.app.completed_jobs_collection.aggregate([
        {"$match": {"task_input_dict.dataset": dataset}},
        {"$sample": {"size": 1}}
    ])

    # Convert cursor type to list
    documents = list(documents)

    # Ensure the list isn't empty (this is just a safety check)
    if not documents:
        raise HTTPException(status_code=404, detail="No image found for the given dataset")

    # Remove the auto generated _id field from the document
    documents[0].pop('_id', None)

    # Return the image in the response
    return {"image": documents[0]}  
    

@router.get("/image/get_random_image_list")
def get_random_image_list(request: Request, dataset: str = Query(...), size: int = Query(1)):  
    # Use Query to get the dataset and size from query parameters

    distinct_documents = []
    tried_ids = set()

    while len(distinct_documents) < size:
        # Use $sample to get 'size' random documents
        documents = request.app.completed_jobs_collection.aggregate([
            {"$match": {"task_input_dict.dataset": dataset, "_id": {"$nin": list(tried_ids)}}},  # Exclude already tried ids
            {"$sample": {"size": size - len(distinct_documents)}}  # Only fetch the remaining needed size
        ])

        # Convert cursor type to list
        documents = list(documents)
        distinct_documents.extend(documents)

        # Store the tried image ids
        tried_ids.update([doc["_id"] for doc in documents])

        # Ensure only distinct images are retained
        seen = set()
        distinct_documents = [doc for doc in distinct_documents if doc["_id"] not in seen and not seen.add(doc["_id"])]

    for doc in distinct_documents:
        doc.pop('_id', None)  # remove the auto generated field
    
    # Return the images as a list in the response
    return {"images": distinct_documents}


@router.get("/image/random_date_range")
def get_random_image_date_range(request: Request, dataset : str = None, start_date: str = None, end_date: str = None):

    query = {
        'task_input_dict.dataset': dataset
    }

    # Update the query based on provided start_date and end_date
    if start_date and end_date:
        query['task_creation_time'] = {'$gte': start_date, '$lte': end_date}
    elif start_date:
        query['task_creation_time'] = {'$gte': start_date}
    elif end_date:
        query['task_creation_time'] = {'$lte': end_date}

    documents = request.app.completed_jobs_collection.aggregate([
        {"$match": query},
        {"$sample": {"size": 1}}
    ])

    # convert curser type to list
    documents = list(documents)
    if len(documents) == 0:
        return []

    # get only the first index
    document = documents[0]

    # remove the auto generated field
    document.pop('_id', None)

    return document

@router.get("/image/data-by-filepath")
def get_image_data_by_filepath(request: Request, file_path: str = None):

    bucket_name, file_path = separate_bucket_and_file_path(file_path)

    image_data = cmd.get_file_from_minio(request.app.minio_client, bucket_name, file_path)

    # Load data into memory
    content = image_data.read()

    response = Response(content=content, media_type="image/jpeg")

    return response

@router.get("/image/list-metadata")
def get_images_metadata(
    request: Request,
    dataset: str = None,
    limit: int = 20,
    offset: int = 0,
    start_date: str = None,
    end_date: str = None
):
    
    print(f"start_date: {start_date}") 

    # Construct the initial query
    query = {
        '$or': [
            {'task_type': 'image_generation_task'},
            {'task_type': 'inpainting_generation_task'}
        ],
        'task_input_dict.dataset': dataset
    }

    # Update the query based on provided start_date and end_date
    if start_date and end_date:
        query['task_creation_time'] = {'$gte': start_date, '$lte': end_date}
    elif start_date:
        query['task_creation_time'] = {'$gte': start_date}
    elif end_date:
        query['task_creation_time'] = {'$lte': end_date}

    print(f"query: {query}") 
    jobs = request.app.completed_jobs_collection.find(query).sort('task_creation_time', -1).skip(offset).limit(limit)

    images_metadata = []
    for job in jobs:
        image_meta_data = {
            'dataset': job['task_input_dict']['dataset'],
            'task_type': job['task_type'],
            'image_path': job['task_output_file_dict']['output_file_path'],
            'image_hash': job['task_output_file_dict']['output_file_hash']
        }
        images_metadata.append(image_meta_data)

    return images_metadata

