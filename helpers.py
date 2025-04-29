from typing import Dict, Any
from weaviate import WeaviateClient
from weaviate.agents.classes import PersonalizationAgentGetObjectsResponse
from weaviate.classes.query import Filter


# TA_DEMO_COLLECTION = "ForumPostSmall"  # For smaller collection
TA_DEMO_COLLECTION = "ForumPost"  # Full-size forum posts collection
PA_DEMO_COLLECTION = "Movie"  # Movie collection

TECHNICAL_DOMAIN_CATEGORIES = {
    "server_setup": "Setup and configuration of the Weaviate database server",
    "ingestion": "Ingesting data into Weaviate, including collection configuration, creation and data import such as batch imports",
    "queries": "Querying Weaviate, including vector, keyword, and hybrid queries",
    "deployment": "Deployment of Weaviate, including Docker, Kubernetes, and cloud deployment",
    "security": "Security-related issues, including authentication, authorization, and data protection",
    "integration": "About integrating Weaviate with other systems or tools",
    "others": "Others not covered by the above categories",
}

ROOT_CAUSE_CATEGORIES = {
    "conceptual_misunderstanding": "A misunderstanding of Weaviate's underlying concepts or specific functionality",
    "incorrect_configuration": "Incorrect configuration of Weaviate or its components",
    "incorrect_usage": "Incorrect usage of Weaviate, such as incorrect API calls or queries",
    "data_modeling": "Issues related to data modeling, such as schema design or data relationships",
    "performance": "Performance-related issues, such as slow queries or high resource usage",
    "bug_or_limit": "A bug or limitation in Weaviate, not allowing the user to do what they wanted",
    "other": "Others not covered by the above categories",
}

ACCESS_CONTEXT_CATEGORIES = {
    "python_client": "Using the offcial Weaviate Python client library",
    "ts_client": "Using the offcial Weaviate JavaScript/TypeScript client library",
    "go_client": "Using the offcial Weaviate Go/Golang client library",
    "java_client": "Using the offcial Weaviate Java client library",
    "cloud_console": "Through the Weaviate Cloud console",
    "llm_framework": "Through an LLM framework, such as LangChain or LlamaIndex",
    "rest_api": "Using the Weaviate REST API directly, including GraphQL queries",
    "other": "Others not covered by the above categories",
}


def get_ta_status(agent_instance, workflow_id):
    # Rough code to check the status of the TA workflow
    import time
    from datetime import datetime, timezone

    while True:
        status = agent_instance.get_status(workflow_id=workflow_id)

        if status["status"]["state"] != "running":
            break

        # Parse start_time and make it timezone-aware (assuming it's in UTC)
        start = datetime.strptime(status["status"]["start_time"], "%Y-%m-%d %H:%M:%S")
        start = start.replace(tzinfo=timezone.utc)

        # Get current time in UTC
        now = datetime.now(timezone.utc)

        # Calculate elapsed time
        elapsed = (now - start).total_seconds()

        print(f"Waiting... Elapsed time: {elapsed:.2f} seconds")
        time.sleep(10)

    # Calculate total time
    if status["status"]["total_duration"]:
        total = status["status"]["total_duration"]
    else:
        start = datetime.strptime(status["status"]["start_time"], "%Y-%m-%d %H:%M:%S")
        end = (
            datetime.now()
            if not status["status"]["end_time"]
            else datetime.strptime(status["status"]["end_time"], "%Y-%m-%d %H:%M:%S")
        )
        total = (end - start).total_seconds()

    print(f"Total time: {total:.2f} seconds")
    print(status)


def load_movie_row(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Load movie data to output matching Weaviate object

    Args:
        item: Dictionary containing movie data with original keys

    Returns:
        Dictionary matching Weaviate data schema
    """
    if item.get("Genre"):
        genres = [genre.strip() for genre in item["Genre"].split(",") if genre.strip()]
    else:
        genres = []

    if item.get("Original_Language"):
        original_language = item["Original_Language"].lower()
    else:
        original_language = ""

    if item.get("Vote_Average"):
        try:
            vote_average = float(item["Vote_Average"])
        except ValueError:
            vote_average = 0.0
    else:
        vote_average = 0.0

    if item.get("Vote_Count"):
        try:
            vote_count = int(item["Vote_Count"])
        except ValueError:
            vote_count = 0
    else:
        vote_count = 0

    if item.get("Popularity"):
        try:
            popularity = float(item["Popularity"])
        except ValueError:
            popularity = 0.0
    else:
        popularity = 0.0

    return {
        "release_date": item["Release_Date"],
        "title": item["Title"],
        "overview": item["Overview"],
        "genres": genres,
        "vote_average": vote_average,
        "vote_count": vote_count,
        "popularity": popularity,
        "poster_url": item["Poster_Url"],
        "original_language": original_language,
    }


def confirm_to_delete(client: WeaviateClient, collection_name: str):
    if client.collections.exists(collection_name):
        confirmation = input(
            f"Collection '{collection_name}' already exists. Do you want to delete it? (y/n): "
        )
        if confirmation.lower() == "y":
            client.collections.delete(collection_name)
        else:
            print("Moving on without deleting the collection.")


def compare_genre_match_scores(
    responses: list,
    preferred_genres: set[str],
    top_n: int = 10,
    response_labels: list[str] = None,
) -> None:
    """
    Compare genre match scores across multiple response sets.

    Args:
        responses (list): List of response objects, each with an .objects attribute (list of movie objects).
        preferred_genres (set[str]): Set of user's preferred genres.
        top_n (int): Number of top results to compare.
        response_labels (list[str], optional): Labels for each response set (e.g., ["Personalized", "No Personalization"]).
    """
    MAX_TITLE_LENGTH = 37

    def truncate_title(title: str, max_length: int = MAX_TITLE_LENGTH) -> str:
        """Truncate a movie title to a maximum length, adding ellipsis if needed."""
        return title[:max_length] + "..." if len(title) > max_length else title

    def genre_match_score(movie_genres, preferred_genres):
        """Count the number of matching genres."""
        return len(set(movie_genres) & preferred_genres)

    num_sets = len(responses)
    if response_labels is None:
        response_labels = [f"Set {i+1}" for i in range(num_sets)]

    # Print header
    header = "Rank".ljust(5)
    for label in response_labels:
        header += f"{label + ' Title':<40}{label + ' Genres':<40}{'Score':<7}"
        header += " | " if label != response_labels[-1] else ""
    print(header)
    print("-" * (num_sets * 87 + 5))

    # Initialize total scores
    total_scores = [0 for _ in range(num_sets)]

    # Print rows
    for i in range(top_n):
        row = f"{i+1:<5}"
        for idx, response in enumerate(responses):
            obj = response.objects[i] if i < len(response.objects) else None
            title = truncate_title(obj.properties["title"]) if obj else ""
            genres = obj.properties.get("genres", []) if obj else []
            genres_str = ", ".join(genres)
            score = genre_match_score(genres, preferred_genres) if obj else 0
            total_scores[idx] += score
            row += f"{title:<40}{genres_str:<40}{score:<7}"
            row += " | " if idx != num_sets - 1 else ""
        print(row)

    print("-" * (num_sets * 87 + 5))
    for idx, label in enumerate(response_labels):
        print(f"Total genre match score ({label}): {total_scores[idx]}")


def print_movie_response_details(response: PersonalizationAgentGetObjectsResponse, n_objects: int = 5, verbose = False) -> None:
    if response.ranking_rationale is not None:
        print(f"Ranking rationale: {response.ranking_rationale}")

    for i, obj in enumerate(response.objects[:n_objects]):
        print(f"*****{i}*****")
        print(obj.properties["title"])
        print(obj.properties["genres"])
        if verbose:
            print(obj.properties["overview"])
            print(obj.properties["release_date"])
            print(f"vote_average: {obj.properties['vote_average']}")
            print(f"vote_count: {obj.properties['vote_count']}")
            print(f"popularity: {obj.properties['popularity']}")
        if obj.original_rank is not None:
            print(f"original rank: {obj.original_rank}, personalized rank: {obj.personalized_rank}")


def compare_genre_match_scores(
    responses: list,
    preferred_genres: set[str],
    top_n: int = 10,
    response_labels: list[str] = None,
) -> None:
    """
    Compare genre match scores across multiple response sets.

    Args:
        responses (list): List of response objects, each with an .objects attribute (list of movie objects).
        preferred_genres (set[str]): Set of user's preferred genres.
        top_n (int): Number of top results to compare.
        response_labels (list[str], optional): Labels for each response set (e.g., ["Personalized", "No Personalization"]).
    """
    MAX_TITLE_LENGTH = 37

    def truncate_title(title: str, max_length: int = MAX_TITLE_LENGTH) -> str:
        """Truncate a movie title to a maximum length, adding ellipsis if needed."""
        return title[:max_length] + "..." if len(title) > max_length else title

    def genre_match_score(movie_genres, preferred_genres):
        """Count the number of matching genres."""
        return len(set(movie_genres) & preferred_genres)

    num_sets = len(responses)
    if response_labels is None:
        response_labels = [f"Set {i+1}" for i in range(num_sets)]

    # Print header
    header = "Rank".ljust(5)
    for label in response_labels:
        header += f"{label + ' Title':<40}{label + ' Genres':<40}{'Score':<7}"
        header += " | " if label != response_labels[-1] else ""
    print(header)
    print("-" * (num_sets * 87 + 5))

    # Initialize total scores
    total_scores = [0 for _ in range(num_sets)]

    # Print rows
    for i in range(top_n):
        row = f"{i+1:<5}"
        for idx, response in enumerate(responses):
            obj = response.objects[i] if i < len(response.objects) else None
            title = truncate_title(obj.properties["title"]) if obj else ""
            genres = obj.properties.get("genres", []) if obj else []
            genres_str = ", ".join(genres)
            score = genre_match_score(genres, preferred_genres) if obj else 0
            total_scores[idx] += score
            row += f"{title:<40}{genres_str:<40}{score:<7}"
            row += " | " if idx != num_sets - 1 else ""
        print(row)

    print("-" * (num_sets * 87 + 5))
    for idx, label in enumerate(response_labels):
        print(f"Total genre match score ({label}): {total_scores[idx]}")


def get_movie_uuid(client: WeaviateClient, title: str):

    movies_collection = client.collections.get(PA_DEMO_COLLECTION)

    response = movies_collection.query.fetch_objects(
        filters=Filter.by_property("title").equal(title),
        limit=1
    )

    if len(response.objects) == 0:
        print(f"Movie '{title}' not found in the collection. Trying to find a title containing all words...")
        response = movies_collection.query.fetch_objects(
            filters=Filter.by_property("title").contains_all(title),
            limit=1
        )

    if len(response.objects) == 0:
        print(f"Movie '{title}' not found in the collection. Trying to find a best matching title...")
        response = movies_collection.query.hybrid(
            query=title,
            limit=1
        )

    if len(response.objects) == 0:
        print(f"Movie '{title}' or similar not found in the collection")
        return None

    print(f"Fetched movie '{title}' from the collection")
    movie = response.objects[0]

    return movie.uuid

