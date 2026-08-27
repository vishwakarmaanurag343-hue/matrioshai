"""MATRIOSHAI Notepad capability layer.

Slice 1: @ai (executable, routes through existing call_llm_structured)
         @browser (recognized only, never executed)

This module does NOT define a new LLM gateway, task engine, or approval engine.
It consumes the existing provider_chain.call_llm_structured and the existing
confirmation_system. Persistence is in-process + markdown intent block only.
"""
