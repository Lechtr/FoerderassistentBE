from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}

@app.get("/retrieve-data")
async def retrieve_data():
    # Example data retrieval logic
    data = {"data": "This is some data"}
    return data


https://www.foerderdatenbank.de/SiteGlobals/FDB/Forms/Suche/Startseitensuche_Formular.html?resourceId=86eabea6-8d08-40e7-a272-b337e51c6613&filterCategories=FundingProgram&submit=Suchen&templateQueryString=&pageLocale=de&sortOrder=dateOfIssue_dt+%2B+asc
https://www.foerderdatenbank.de/SiteGlobals/FDB/Forms/Suche/Startseitensuche_Formular.html?submit=Suchen&filterCategories=FundingProgram&sortOrder=dateOfIssue_dt+desc