# scheduler/chains.py
import datetime
import json
from typing import Dict, Any
from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI
from .config.prompts import (
    time_inference_prompt, 
    priority_prompt,
    time_parser,
    priority_parser
)

def create_schedule_chain():
    """기존 일정 추출 체인 생성 (기존 코드에서 가져옴)"""
    # 기존 app.py의 create_schedule_chain 함수 코드를 여기로 이동

def create_enhancement_chain():
    """시간 추론 및 우선순위 분석 체인 생성"""
    llm = ChatOpenAI(
        model_name="gpt-4",  # 또는 "gpt-3.5-turbo"
        temperature=0
    )
    
    time_chain = LLMChain(
        llm=llm, 
        prompt=time_inference_prompt, 
        output_parser=time_parser,
        verbose=True
    )
    
    priority_chain = LLMChain(
        llm=llm, 
        prompt=priority_prompt, 
        output_parser=priority_parser,
        verbose=True
    )
    
    return {
        "time_chain": time_chain,
        "priority_chain": priority_chain
    }