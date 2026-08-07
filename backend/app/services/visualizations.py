import pandas as pd


def recommend_visualizations(
    df: pd.DataFrame,
    recommendations: list,
    column_profiles: list,
) -> list[dict]:

    visualizations = []


    for recommendation in recommendations:

        analysis_type = recommendation.get(
            "analysis_type"
        )


        if analysis_type == "time_series":

            visualization = build_time_series(
                column_profiles,
                recommendation,
            )


        elif analysis_type == "contribution":

            visualization = build_contribution(
                column_profiles,
                recommendation,
            )


        elif analysis_type == "relationship":

            visualization = build_relationship(
                column_profiles,
                recommendation,
            )


        elif analysis_type == "outlier_detection":

            visualization = build_outliers(
                column_profiles,
                recommendation,
            )

        else:
            continue


        if visualization:
            visualizations.append(
                visualization
            )


    return visualizations



def build_time_series(
    column_profiles,
    recommendation,
):

    date_column = find_column(
        column_profiles,
        role="date",
    )

    measure_column = find_column(
        column_profiles,
        role="measure",
        keywords=recommendation.get(
            "measure_keywords",
            []
        ),
    )


    if not date_column or not measure_column:
        return None


    return {
        "id": recommendation["id"],
        "title": recommendation["title"],
        "chart": "line",
        "x": date_column,
        "y": measure_column,
        "reason": recommendation["description"],
        "priority": recommendation["priority"],
    }



def build_contribution(
    column_profiles,
    recommendation,
):

    dimension = find_column(
        column_profiles,
        role="dimension",
        keywords=recommendation.get(
            "dimension_keywords",
            [],
        ),
    )

    measure = find_column(
        column_profiles,
        role="measure",
        keywords=recommendation.get(
            "measure_keywords",
            [],
        ),
    )


    if not dimension or not measure:
        return None


    return {
        "id": recommendation["id"],
        "title": recommendation["title"],
        "chart": "bar",
        "x": dimension,
        "y": measure,
        "reason": recommendation["description"],
        "priority": recommendation["priority"],
    }



def build_relationship(
    column_profiles,
    recommendation,
):

    measure = find_column(
        column_profiles,
        role="measure",
        keywords=recommendation.get(
            "measure_keywords",
            [],
        ),
    )

    if not measure:
        return None


    measure_columns = [
        col["name"]
        for col in column_profiles
        if col["role"] == "measure"
    ]


    if len(measure_columns) < 2:
        return None


    return {
        "id": recommendation["id"],
        "title": recommendation["title"],
        "chart": "scatter",
        "x": measure_columns[0],
        "y": measure_columns[1],
        "reason": recommendation["description"],
        "priority": recommendation["priority"],
    }



def build_outliers(
    column_profiles,
    recommendation,
):

    measure = find_column(
        column_profiles,
        role="measure",
        keywords=recommendation.get(
            "measure_keywords",
            [],
        ),
    )


    if not measure:
        return None


    return {
        "id": recommendation["id"],
        "title": recommendation["title"],
        "chart": "scatter",
        "x": measure,
        "reason": recommendation["description"],
        "priority": recommendation["priority"],
    }



def find_column(
    column_profiles,
    role=None,
    keywords=None,
):

    keywords = keywords or []


    # First filter by role
    candidates = [
        column["name"]
        for column in column_profiles
        if column["role"] == role
    ]


    # Then use keywords as a preference
    for column in candidates:

        column_name = column.lower()

        if any(
            keyword in column_name
            for keyword in keywords
        ):
            return column


    # If no keyword match,
    # return first valid role match
    if candidates:
        return candidates[0]


    return None