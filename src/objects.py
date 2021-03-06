# standard modules
import traceback
from datetime import datetime

# 3rd party modules
from fastapi import HTTPException
import paramiko
from pyodbc import Error

# application modules
from src.config import config
from src.utils import get_db_cursor


class Collection(object):

    def __init__(self, id: int, name: str=None, sample_needed_per_label: int=None, duration_in_seconds_per_sample: int=None, *args, **kwargs):
        self.id = id
        if not name is None:
            self.name = name
        if not sample_needed_per_label is None:
            self.sample_needed_per_label = sample_needed_per_label
        if not duration_in_seconds_per_sample is None:
            self.duration_in_seconds_per_sample = duration_in_seconds_per_sample

    @classmethod
    def get_all(cls):
        cursor = get_db_cursor()
        sql_query = """SELECT CollectionId AS Id, Name, SampleDurationInSeconds, SamplesPerLabel 
                    FROM Collections WHERE IsActive = 1"""
        collections = None
        try:
            with cursor:
                result = cursor.execute(sql_query)
                collections = result.fetchall()
        except Exception as e:
            message = "Cannot fetch collections"
            raise HTTPException(detail=message, status_code=409)
        collection_instances = []
        for collection in collections:
            collection_instances.append(cls(collection.Id, name=collection.Name, duration_in_seconds_per_sample=collection.SampleDurationInSeconds, sample_needed_per_label=collection.SamplesPerLabel))
        return collection_instances

    @classmethod
    def create(cls, sample_needed_per_label:int, duration_in_seconds_per_sample:int, name: str=None, *args, **kwargs):
        cursor = get_db_cursor()
        sql_query = f"EXEC CreateCollections @SampleDurationInSeconds={duration_in_seconds_per_sample}, @SamplesPerLabel={sample_needed_per_label}, @Name='{name}'"
        created_collection = None
        try:
            with cursor:
                result = cursor.execute(sql_query)
                created_collection = result.fetchone()
        except Exception as e:
            message = f"Cannot create collection with name - {name}"
            if isinstance(e, Error) and e.args[1].find('52000') != -1:
                message = f"a collection with given name - '{name}', already exists"
            raise HTTPException(detail=message, status_code=409)
        return cls(created_collection.Id, name=name, sample_needed_per_label=sample_needed_per_label, duration_in_seconds_per_sample=duration_in_seconds_per_sample)
    
    def add_labels(self, labels):
        cursor = get_db_cursor()
        labels_csv = ""
        for label in labels:
            labels_csv += str(label) + ','
        labels_csv = labels_csv[:-1]
        sql_query = f"EXEC CreateCollectionLabelMapping @CollectionId={self.id}, @Labels='{labels_csv}'"
        created_mappings = None
        try:
            with cursor:
                result = cursor.execute(sql_query)
                created_mappings = result.fetchall()
        except Exception as e:
            message = f"Cannot map collection '{self.id}' with labels - {labels_csv}"
            raise HTTPException(detail=message, status_code=409)
        created_mappings_list = []
        for created_mapping in created_mappings:
            created_mappings_list.append({"label": Label(created_mapping.LabelId, name=created_mapping.LabelName), "collection": Collection(created_mapping.CollectionId, name=created_mapping.CollectionName)})
        return created_mappings_list

class Label(object):

    def __init__(self, id: int, name: str=None, sample_count: int=None, *args, **kwargs):
        self.id = id
        if name:
            self.name = name
        if not sample_count is None:
            self.sample_count = sample_count

    @classmethod
    def create(cls, name:str):
        cursor = get_db_cursor()
        sql_query = f"EXEC CreateLabels @LabelName = '{name}'"
        try:
            with cursor:
                result = cursor.execute(sql_query)
                created_label = result.fetchone()
        except Exception as e:
            message = f"Cannot create label with name - {name}"
            if isinstance(e, Error) and e.args[1].find('52000') != -1:
                message = f"a label with given name - '{name}', already exists"
            raise HTTPException(detail=message, status_code=409)
        return cls(created_label.Id, name=name, sample_count=0)
    
    @classmethod
    def get_sample_duration_of_labels(cls, label_instance_list):
        cursor = get_db_cursor()
        labels_csv = ""
        for label_instance in label_instance_list:
            labels_csv += str(label_instance.id) + ','
        labels_csv = labels_csv[:-1]
        sql_query = f"EXEC GetSampleDurationsOfLabels @Labels = '{labels_csv}'"
        try:
            with cursor:
                result = cursor.execute(sql_query)
                durations = result.fetchall()
        except Exception as e:
            raise HTTPException(detail=f"Cannot fetch durations of the labels - {labels_csv}", status_code=409)
        if len(durations) == 0:
            return []
        durations_list = []
        for duration in durations:
            durations_list.append(duration.SampleDurationInSeconds)
        return durations_list

    @classmethod
    def get_all(cls):
        cursor = get_db_cursor()
        sql_query = "SELECT LabelId AS Id, Name, SampleCount FROM Labels WHERE IsActive = 1"
        try:
            with cursor:
                result = cursor.execute(sql_query)
                labels = result.fetchall()
        except Exception as e:
            raise HTTPException(detail=f"Cannot fetch labels", status_code=409)
        if len(labels) == 0:
            return []
        labels_list = []
        for label in labels:
            labels_list.append(cls(label.Id, name=label.Name, sample_count=label.SampleCount))
        return labels_list

    def add_to_collection(self, collection):
        cursor = get_db_cursor()
        sql_query = """INSERT INTO voiceapp_collectionsmap(Collection_id, Label_id)
                    SELECT ?, ?"""
        try:
            with cursor:
                cursor.execute(sql_query, collection.id, self.id)
        except Exception as e:
            raise HTTPException(detail=f"Cannot add label - {self.id} to collection {collection.id}", status_code=409)

    def get_collections(self):
        cursor = get_db_cursor()
        sql_query = f"EXEC GetCollections @LabelId={self.id}"
        try:
            with cursor:
                cursor.execute(sql_query)
                result = cursor.fetchall()
        except Exception as e:
            raise HTTPException(detail=f"Cannot fetch Collections of Label - {self.id}", status_code=409)
        collections_list = []
        for collection in result:
            collections_list.append(Collection(collection.Id, name=collection.CollectionName, sample_needed_per_label=collection.SamplesPerLabel, duration_in_seconds_per_sample=collection.SampleDurationInSeconds))
        return collections_list

class SpeechAPI(object):

    def __init__(self, id: int, name: str=None, training_status: int=None, type: str=None):
        self.id = id
        if name:
            self.name = name
        if training_status:
            self.training_status = training_status
        if type:
            self.type = type

    @classmethod
    def create(cls, name, description=None, labels=None):
        cursor = get_db_cursor()
        if not labels or len(labels) == 0:
            raise HTTPException(detail="SpeechAPI needs atleast 1 active label")
        if not description:
            description = name
        sql_query = f"EXEC CreateSpeechAPI @Name='{name}', @Description='{description}', @Labels='{labels}'"
        try:
            with cursor:
                result = cursor.execute(sql_query)
                created_speech_api = result.fetchone()
        except Exception as e:
            message = f"Cannot fetch labels of the SpeechAPI - {name}"
            if isinstance(e, Error) and e.args[1].find('52000') != -1:
                message = f"a speechAPI with given name - '{name}', already exists"
            elif isinstance(e, Error) and e.args[1].find('53000') != -1:
                message = f"{labels} are not active"
            raise HTTPException(detail=message, status_code=409)
        return created_speech_api

    @classmethod
    def get_all(cls):
        cursor = get_db_cursor()
        sql_query = "EXEC GetActiveSpeechAPI"
        try:
            with cursor:
                result = cursor.execute(sql_query)
                speech_apis = result.fetchall()
        except Exception as e:
            raise HTTPException(detail=f"Cannot fetch SpeechAPIs", status_code=409)
        if len(speech_apis) == 0:
            return []
        speech_apis_list = []
        for speech_api in speech_apis:
            speech_apis_list.append(cls(speech_api.Id, name=speech_api.Name, type=speech_api.Type, training_status=speech_api.TrainingStatus))
        return speech_apis_list

    def get_speech_api_versions(self):
        cursor = get_db_cursor()
        sql_query = """SELECT SpeechApi_id AS Id, VersionNumber, IsActive, UpdatedAt AS LastUpdated
                    FROM SpeechApiVersions
                    WHERE SpeechApi_id = ?"""
        try:
            with cursor:
                result = cursor.execute(sql_query, self.id)
                speech_api_versions = result.fetchall()
        except Exception as e:
            raise HTTPException(detail=f"Cannot fetch versions of the SpeechAPI - {self.id}", status_code=409)
        if len(speech_api_versions) == 0:
            return []
        speech_api_versions_list = []
        for speech_api_version in speech_api_versions:
            speech_api_versions_list.append(SpeechAPIVersion(speech_api_version.Id, speech_api=self, version=speech_api_version.VersionNumber, last_updated=speech_api_version.LastUpdated, is_active=speech_api_version.IsActive))
        return speech_api_versions_list
    
    def get_sample_durations(self):
        cursor = get_db_cursor()
        sql_query = "EXEC GetSampleDurations @SpeechAPIId = ?"
        try:
            with cursor:
                result = cursor.execute(sql_query, self.id)
                sample_durations = result.fetchall()
        except Exception as e:
            raise HTTPException(detail=f"Cannot fetch sample durations of the SpeechAPI - {self.id}", status_code=409)
        if len(sample_durations) == 0:
            return []
        sample_durations_list = []
        for sample_duration in sample_durations:
            sample_durations_list.append(sample_duration.SampleDurations)
        return sample_durations_list

    def get_labels_of_speech_api(self, sample_duration):
        cursor = get_db_cursor()
        sql_query = f"EXEC GetLabelsOfSpeechAPI @SpeechAPIId = {self.id}, @SampleDuration = {sample_duration}"
        try:
            with cursor:
                result = cursor.execute(sql_query)
                labels = result.fetchall()
        except Exception as e:
            raise HTTPException(detail=f"Cannot fetch labels of the SpeechAPI - {self.id}", status_code=409)
        labels_list = []
        for label in labels:
            labels_list.append(Label(label.Id, name=label.Name, sample_count=label.SampleCount))
        return labels_list

    def train(self, labels_id_csv, sample_duration_cut_off=5):

        # intentional 2 seperate DB calls
        # get labels names from DB
        cursor = get_db_cursor()
        sql_query = f"EXEC GetLabelNames @LabelIds = '{labels_id_csv}'"
        try:
            with cursor:
                result = cursor.execute(sql_query)
                labels = result.fetchall()
        except Exception as e:
            raise HTTPException(detail=f"Cannot fetch names of the label IDs - {labels_id_csv}", status_code=409)
        label_names_csv = ""
        for label in labels:
            label_names_csv += label.Name + ','
        label_names_csv = label_names_csv[:-1]
        
        if not hasattr(self, "name") or not self.name:
            # get speech api name from DB
            cursor = get_db_cursor()
            sql_query = """SELECT Name 
                        FROM SpeechAPI
                        WHERE SpeechAPIId = ?
                        AND IsActive = 1"""
            try:
                with cursor:
                    result = cursor.execute(sql_query, self.id)
                    speech_api = result.fetchone()
            except Exception as e:
                raise HTTPException(detail=f"Cannot fetch name of the speech API ID - {self.id}", status_code=409)

            if speech_api is None:
                raise HTTPException(detail=f"No active speech API exists with ID - {self.id}", status_code=409)
            
            self.name = speech_api.Name

        # connect to remote shell
        try:
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(hostname=config.gpu_host,username=config.gpu_username,password=config.gpu_password)
            stdin, stdout, stderr = ssh_client.exec_command(f'touch labels.csv')
            stdin, stdout, stderr = ssh_client.exec_command(f'echo "{label_names_csv}" >> "labels.csv"')
            stdin, stdout, stderr = ssh_client.exec_command(f'echo "{sample_duration_cut_off}" >> "labels.csv"')
            stdin, stdout, stderr = ssh_client.exec_command(f'echo "{self.name}" >> "labels.csv"')
            stdin, stdout, stderr = ssh_client.exec_command(f'mv labels.csv /home/mlvgadmin/Data/dev/watch/')
            ssh_client.close()
        except Exception as e:
            raise HTTPException(detail="Cannot trigger training pipeline", status_code=500)

class SpeechAPIVersion(object):

    def __init__(self, id: int, speech_api: SpeechAPI=None, version: str=None, last_updated: datetime=None, is_active: bool=None, *args, **kwargs):
        self.id = id
        if speech_api:
            self.speech_api = speech_api
        if version:
            self.version = version
        if last_updated:
            self.last_updated = last_updated
        if is_active:
            self.is_active = is_active

    def get_labels_of_speech_api_version(self):
        cursor = get_db_cursor()
        sql_query = f"EXEC GetLabelsOfSpeechAPIVersion @SpeechAPIVersionId={self.id}"
        try:
            with cursor:
                result = cursor.execute(sql_query)
                labels = result.fetchall()
        except Exception as e:
            raise HTTPException(detail=f"Cannot fetch labels of the speechAPIVersion - {self.id}", status_code=409)
        if len(labels) == 0:
            return []
        labels_list = []
        for label in labels:
            labels_list.append(Label(label.Id, name=label.Name, sample_count=label.SampleCount))
        return labels_list
