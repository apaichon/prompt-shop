"""Synthetic test workers only. Excluded from the deployment build context."""
import os
import time
from intent_service.protocol import MODEL_REVISION


def success(label="find_item"):
    return {"schema_version":"intent-v1","intent":label,"confidence":.95,"margin":.8,"abstained":False,"reason":None,"model_revision":MODEL_REVISION}


class TinyModel:
    def __init__(self,root): pass
    def predict(self,text):
        if text == "stall": time.sleep(3)
        if text == "crash": os._exit(3)
        if text == "malformed": return {"intent":"execute_payment"}
        return success()


class BadLoad:
    def __init__(self,root): raise ValueError("synthetic loader failure")
