"""TASK-0010 narrow async adapter. Task 3 ToolHost owns turn/attempt/ACK state."""
import asyncio
import json
import math
import os

import httpx

ENDPOINT = "http://127.0.0.1:8003/classify"
MODEL_REVISION = "7b928d828b7b0e022f929d9bd2e44165aa270148"
LABELS = ("find_item", "select_item", "repeat_directions", "out_of_scope")
FIELDS = {"schema_version", "intent", "confidence", "margin", "abstained", "reason", "model_revision"}


def failed(reason="error"):
    return {"schema_version":"intent-v1", "intent":None, "confidence":None, "margin":None,
            "abstained":True, "reason":reason, "model_revision":MODEL_REVISION}


def result(value):
    if not isinstance(value,dict) or set(value)!=FIELDS or value["schema_version"]!="intent-v1" or value["model_revision"]!=MODEL_REVISION or type(value["abstained"]) is not bool:
        raise ValueError("classifier identity differs")
    for key in ("confidence","margin"):
        score=value[key]
        if score is not None and (type(score) not in (int,float) or not math.isfinite(score) or not 0<=score<=1):
            raise ValueError("classifier score invalid")
    if value["confidence"] is not None and value["margin"] is not None and value["margin"] > value["confidence"]:
        raise ValueError("margin exceeds confidence")
    if value["abstained"]:
        if value["intent"] is not None or value["reason"] not in ("low_confidence","timeout","busy","error"):
            raise ValueError("classifier abstention inconsistent")
        if value["reason"]=="low_confidence":
            if value["confidence"] is None or value["margin"] is None or (value["confidence"]>=.7 and value["margin"]>=.15):
                raise ValueError("classifier low-confidence inconsistent")
        elif value["confidence"] is not None or value["margin"] is not None:
            raise ValueError("failed inference cannot report scores")
    elif value["intent"] not in LABELS or value["reason"] is not None or value["confidence"] is None or value["margin"] is None or value["confidence"]<.7 or value["margin"]<.15:
        raise ValueError("classifier success inconsistent")
    return value


def strict_object(pairs):
    out={}
    for key,value in pairs:
        if key in out: raise ValueError("duplicate response field")
        out[key]=value
    return out


class Classifier:
    def __init__(self,token,*,transport=None):
        if not isinstance(token,str) or not 32<=len(token)<=1024 or not token.isascii() or any(ord(c)<33 or ord(c)>126 for c in token):
            raise ValueError("private token configuration invalid")
        self._token,self._transport=token,transport

    async def __call__(self,text):
        if not isinstance(text,str) or not 1<=len(text)<=300 or not text.strip() or "\0" in text:
            return failed()
        try:
            async with asyncio.timeout(1.2):
                async with httpx.AsyncClient(timeout=1.2,trust_env=False,follow_redirects=False,transport=self._transport) as client:
                    async with client.stream("POST",ENDPOINT,headers={"X-Internal-Token":self._token,"Content-Type":"application/json"},json={"text":text}) as response:
                        if response.status_code!=200 or response.headers.get("content-type","").split(";")[0].lower()!="application/json":
                            return failed()
                        body=bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body)>2048: return failed()
                        parsed=json.loads(body,object_pairs_hook=strict_object)
                        body.clear()
                        return result(parsed)
        except asyncio.CancelledError:
            raise
        except (TimeoutError,httpx.TimeoutException):
            return failed("timeout")
        except (httpx.HTTPError,ValueError,UnicodeError):
            return failed()
        finally:
            text=None


async def classify_intent(text: str) -> dict:
    # Endpoint/model/schema are server-owned; none is exposed in tool arguments.
    try:
        classifier=Classifier(os.environ.get("LAYA_INTERNAL_TOKEN",""))
    except ValueError:
        return failed()
    return await classifier(text)
