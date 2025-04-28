import weaviate
from weaviate.classes.init import Auth
from weaviate.classes.config import Configure, DataType, Property
from weaviate.util import generate_uuid5
from weaviate.agents.personalization import PersonalizationAgent
from weaviate.classes.config import DataType
from uuid import uuid4
from datasets import load_dataset
from helpers import confirm_to_delete, PA_DEMO_COLLECTION
from helpers import load_movie_row
from tqdm import tqdm
import os
from dotenv import load_dotenv

weaviate_url = os.getenv("WEAVIATE_URL")
weaviate_key = os.getenv("WEAVIATE_API_KEY")
load_dotenv()

client = weaviate.connect_to_weaviate_cloud(
    cluster_url=weaviate_url, auth_credentials=Auth.api_key(weaviate_key)
)

confirm_to_delete(client, PA_DEMO_COLLECTION)

client.collections.create(
    PA_DEMO_COLLECTION,
    description="A dataset that lists clothing items, their brands, prices, and more.",
    vectorizer_config=Configure.Vectorizer.text2vec_weaviate(
        model="Snowflake/snowflake-arctic-embed-m-v1.5"
    ),
    properties=[
        Property(
            name="release_date",
            data_type=DataType.TEXT,
            description="release date of the movie",
            skip_vectorization=True,
        ),
        Property(
            name="title", data_type=DataType.TEXT, description="title of the movie"
        ),
        Property(
            name="overview",
            data_type=DataType.TEXT,
            description="overview of the movie",
        ),
        Property(
            name="genres",
            data_type=DataType.TEXT_ARRAY,
            description="genres of the movie",
        ),
        Property(
            name="vote_average",
            data_type=DataType.NUMBER,
            description="vote average of the movie",
        ),
        Property(
            name="vote_count",
            data_type=DataType.INT,
            description="vote count of the movie",
        ),
        Property(
            name="popularity",
            data_type=DataType.NUMBER,
            description="popularity of the movie",
        ),
        Property(
            name="poster_url",
            data_type=DataType.TEXT,
            description="poster path of the movie",
            skip_vectorization=True,
        ),
        Property(
            name="original_language",
            data_type=DataType.TEXT,
            description="Code of the language of the movie",
            skip_vectorization=True,
        ),
    ],
)

# Load the movies dataset
movies_dataset = load_dataset("Pablinho/movies-dataset", split="train", streaming=True)

# Get the Movies collection
movies_collection = client.collections.get(PA_DEMO_COLLECTION)

# Batch import the appropriate data
with movies_collection.batch.fixed_size(batch_size=200) as batch:
    for item in tqdm(movies_dataset):
        data_object = load_movie_row(item)
        batch.add_object(properties=data_object)

if PersonalizationAgent.exists(client, PA_DEMO_COLLECTION):
    pa = PersonalizationAgent.connect(client=client, reference_collection=PA_DEMO_COLLECTION)
else:
    pa = PersonalizationAgent.create(
        client=client,
        reference_collection=PA_DEMO_COLLECTION,
        user_properties={
            "age": DataType.NUMBER,
            "favorite_genres": DataType.TEXT_ARRAY,
            "favorite_years": DataType.NUMBER_ARRAY,
            "language": DataType.TEXT,
        },
    )

persona_id = generate_uuid5("sebawita")  # To generate a deterministic UUID

pa.delete_persona(persona_id)
