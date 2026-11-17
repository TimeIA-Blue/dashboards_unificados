from pandas import DataFrame


def dataframe_to_csv(df: DataFrame) -> bytes:
    download_df = df.copy()
    for column in download_df.select_dtypes(include=["datetime", "datetimetz"]):
        download_df[column] = download_df[column].dt.strftime("%d/%m/%Y %H:%M:%S")
    for column in download_df.select_dtypes(include=["float"]):
        download_df[column] = download_df[column].round(2)
    return download_df.to_csv(index=False).encode("utf-8")
