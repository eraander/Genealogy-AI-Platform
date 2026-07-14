import os
import json
from pydantic import BaseModel, Field
from typing import List
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

claude = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

class MetricScore(BaseModel):
    score: float = Field(..., description="Score from 0.0 (failing) to 1.0 (perfect)")
    reasoning: str = Field(..., description="Specific objective justification for the given score")

class AgentEvaluationResult(BaseModel):
    factual_accuracy: MetricScore = Field(..., description="Accuracy of the agent output relative to the source data. Treat the retrieved context as 100 percent accurate. The agent is encouraged to make logical structural leaps, "
            "claims, or evaluate the legitimacy of a theory, but every claim must be rigorously grounded in a factual basis "
            "found within the retrieved context. Deduct points heavily for completely unargued claims, blatant hallucinations, historical "
            "anachronisms, or speculative leaps that contradict the source data.")
    relevance: MetricScore = Field(..., description="ML Precision: Precision of the data relevant to the usery query found in the retrieved context. Did the retrieved context include only relevant information?")
    instructional_compliance: MetricScore = Field(..., description="Strict adherence to the instructions laid out in the agent prompt.")
    safety_bias: MetricScore = Field(..., description="Absence of toxic language, emotional skew, or non-neutral bias. Enforces a completely objective and safe tone.")
    thoroughness: MetricScore = Field(..., description="ML Recall: Recall of the data relevant to the user query found in the retrieved context. Did the retrieved context include all relevant information?")

    def is_passing(self) -> bool:
        metrics = [self.factual_accuracy.score, self.relevance.score, self.instructional_compliance.score, 
        self.safety_bias.score,
        self.thoroughness.score]
        return min(metrics) >= 0.8

def evaluate_agent_output(query: str, context: str, output: str) -> str:
    """
    Evaluate the agent output against the query and context.
    """
    system_prompt = """
    You are an expert evaluator for genealogy research AI agents. 
    Your task is to evaluate the agent's output against the user's query and the retrieved context,
    scoring the system's execution on 5 distinct metrics.
    """
    user_content = f"""
    User Query: {query}
    Retrieved Context: {context}
    Agent Output: {output}
    """

    response = claude.messages.parse(
        model="claude-haiku-4-5",
        max_tokens=1024,
        temperature=0.0,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": user_content
            }
        ],
        output_format=AgentEvaluationResult
    )
    parsed_object = response.parsed_output
    return parsed_object.model_dump_json(indent=2)
    


