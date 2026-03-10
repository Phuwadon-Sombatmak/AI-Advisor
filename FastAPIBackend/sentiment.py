from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
import torch

_sentiment_pipeline = None


def get_sentiment_pipeline():
    global _sentiment_pipeline

    if _sentiment_pipeline is None:

        model_name = "yiyanghkust/finbert-tone"

        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)

        device = 0 if torch.cuda.is_available() else -1

        _sentiment_pipeline = pipeline(
            task="sentiment-analysis",
            model=model,
            tokenizer=tokenizer,
            device=device
        )

    return _sentiment_pipeline


def score_text(text: str) -> float:
    """
    คืนค่า sentiment score

    Positive  -> +score
    Negative  -> -score
    Neutral   -> 0
    """

    if not text or len(text.strip()) == 0:
        return 0.0

    pipe = get_sentiment_pipeline()

    try:
        result = pipe(text[:512])[0]
    except Exception:
        return 0.0

    label = result["label"].upper()
    score = float(result["score"])
    
    if label == "POSITIVE" and score > 0.55:
        return score

    elif label == "NEGATIVE" and score > 0.55:
        return -score

    else:
        return 0