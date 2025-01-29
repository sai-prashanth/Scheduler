import requests
import json
from src.config import OPENROUTER_API_KEY, MODEL

def ask_llm(model: str, prompt: str, json_mode: bool = False) -> str:
    """
    Calls the OpenRouter API to get a chat completion using the specified model and prompt.
    
    :param model_name: The model to use, e.g. 'openai/gpt-4o'
    :param prompt: The user query or message to send to the model
    :return: The text response returned by the model
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    }
    
    if json_mode:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "response_format": {
                "type": "json_object"
            },
        }
    else:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
        }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        response.raise_for_status()  # Raises an exception if the request was unsuccessful
        data = response.json()

        # Typically, the assistant response is in data["choices"][0]["message"]["content"]
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as req_err:
        return f"Request error: {req_err}"
    except KeyError:
        return f"Unexpected response format from OpenRouter. Response: {response.text}"


def create_prompt(prompt_template: str, **kwargs) -> str:
    """
    Creates a prompt by filling in the placeholders in the template with the provided keyword arguments.
    
    :param prompt_template: The template string with placeholders for the variables
    :param kwargs: The keyword arguments to fill in the placeholders
    :return: The prompt string with the placeholders replaced by the values
    """
    return prompt_template.format(**kwargs)

if __name__ == "__main__":
    # model = "google/gemini-2.0-flash-exp:free"
    model = MODEL
    prompt_template = "What is the capital of {country}?"
    prompt = create_prompt(prompt_template, country="India")
    response = ask_llm(model, prompt)
    print(response)