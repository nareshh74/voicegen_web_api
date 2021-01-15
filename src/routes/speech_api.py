# 3rd party modules
from fastapi import APIRouter
from fastapi.responses import ORJSONResponse

# application modules
from src.objects import SpeechAPI, SpeechAPIVersion, Label
from src import DTO
from src.responses import CustomResponse


router = APIRouter(
    prefix="/speechAPI",
    tags=["SpeechAPI"]
)


@router.get("", response_model=DTO.GetAllSpeechAPIsOut, status_code=200)
def get_all_speech_apis():
    speech_apis_list = SpeechAPI.get_all()
    return CustomResponse(content={"speechAPIs": speech_apis_list})

@router.get("/{speechAPIId}/speechAPIVersion", response_model=DTO.GetAllSpeechAPIVersionsOut, status_code=200)
def get_all_speech_api_versions(speechAPIId: int):
    speech_api = SpeechAPI(speechAPIId)
    speech_api_versions_list = speech_api.get_speech_api_versions()
    return CustomResponse(content={"speechAPIVersions": speech_api_versions_list})

@router.get("/{speechAPIId}/speechAPIVersion/{speechAPIVersionId}/labels", response_model=DTO.GetLabelsOfSpeechAPIVersionOut, status_code=200)
def get_labels_of_speech_api_version(speechAPIId: int, speechAPIVersionId: int):
    speech_api = SpeechAPI(speechAPIId)
    speech_api_version = SpeechAPIVersion(speechAPIVersionId, speech_api=speech_api)
    labels_list = speech_api_version.get_labels_of_speech_api_version()
    return CustomResponse(content={"labels": labels_list})

@router.get("/{speechPAIId}/labels", response_model=DTO.GetLabelsOfSpeechAPIOut, status_code=200)
def get_labels_of_speech_api(speechAPIId: int):
    speech_api = SpeechAPI(speechAPIId)
    labels_list = speech_api.get_labels_of_speech_api()
    return CustomResponse(content={"labels": labels_list}, status_code=200)

@router.post("/{speechAPIId}/train", response_model=DTO.SuccessResponse, status_code=200)
def train_speech_api(speechAPIId: int, payload: DTO.TrainSpeechAPIIn):
    speech_api = SpeechAPI(speechAPIId)
    labels_list = []
    for label_id in payload.labels:
        labels_list.append(Label(label_id))
    speech_api.train(labels_list, payload.sampleDuration)
    return CustomResponse()
