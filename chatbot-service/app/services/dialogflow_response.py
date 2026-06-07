from app.schemas.dialogflow import DialogflowCXResponse


def text_response(message: str, parameters: dict | None = None) -> DialogflowCXResponse:
    response = {
        "fulfillmentResponse": {
            "messages": [
                {
                    "text": {
                        "text": [message],
                    }
                }
            ]
        }
    }
    if parameters:
        response["sessionInfo"] = {"parameters": parameters}
    return DialogflowCXResponse.model_validate(response)


def rich_response(markdown: str, payload: dict, parameters: dict | None = None) -> DialogflowCXResponse:
    response = {
        "fulfillmentResponse": {
            "messages": [
                {
                    "text": {
                        "text": [markdown],
                    }
                },
                {
                    "payload": payload,
                },
            ]
        }
    }
    if parameters:
        response["sessionInfo"] = {"parameters": parameters}
    return DialogflowCXResponse.model_validate(response)
