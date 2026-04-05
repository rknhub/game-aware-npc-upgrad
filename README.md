# Game-Aware NPC: Player-Based NPC Behaviour Generation for Blockchain Gaming

**Author:** Ramesh Krishnan  
**Programme:** MSc Machine Learning — Liverpool John Moores University (upGrad MSML C26)  
**Submitted:** April 2026

---

## Overview

This repository contains all research notebooks for the thesis *"Game-Aware NPC: Player Based NPC Behavior Generation for Blockchain Gaming."*

The project builds **Whisper**, an AI-powered merchant NPC for a purpose-built text-adventure game — *Origins of Lume: Gate of Whispers*. Whisper combines:

- A fine-tuned **Qwen2.5-7B-Instruct** model (QLoRA) for contextual dialogue generation
- A **hybrid epsilon-greedy + UCB contextual bandit** RL agent with four independent decision bandits (discount, urgency, upsell, loan)
- **Blockchain-verified memory and asset ownership** via ERC-721 smart contracts on Polygon Amoy testnet

A within-subjects user study (n=15) compared Alpha (traditional button-based shop) vs Beta (AI/blockchain NPC) conditions across four research questions: engagement and revenue (RQ1), trust (RQ2), RL trading strategies (RQ3), and minimum viable architecture (RQ4).

---

## Notebook Pipeline

The notebooks follow the development pipeline in order. Run them sequentially for full reproducibility.

---

### 01 — Player Clustering
`01_player_clustering.ipynb`

Exploratory data analysis and K-Means clustering (k=6) on the Kaggle Online Gaming Behaviour dataset (40,034 samples, 13 features). Identifies six player archetypes that drive NPC merchant strategy — most critically, that only one cluster (Spender, ~20% of players) makes purchases, informing Whisper's adaptive pricing logic.

**Outputs:** Six labelled player archetypes, cluster centroids, archetype-to-NPC-strategy mapping.

---

### 02A — Dialogue Dataset (Primary Pipeline)
`02v2_PartA_Dialogue_dataset_complete.ipynb`

Constructs the primary synthetic training dataset. Generates 16,380 structured merchant dialogue samples via GPT-4o-mini across seven interaction types, six player archetypes, and three relationship levels. Establishes the ChatML format used throughout training.

**Outputs:** Base training dataset in ChatML format.

---

### 02B — Cornell Persuasion Integration
`02v2_PartB_ModalV2_Cornell_Persuasion.ipynb`

Transforms the Cornell Persuasion For Good dataset (1,017 dialogues, 20,932 utterances) into merchant-appropriate training samples. Maps seven academic persuasion strategies — including credibility appeal, foot-in-the-door, and emotional appeal — onto Whisper's dialogue modes.

**Outputs:** 1,750 persuasion-strategy samples merged into the training pipeline.

---

### 03 — Qwen Training Data Generation
`03V7_Qwen_Training_Data_Generation.ipynb`

Full regeneration of training data for Qwen2.5-7B migration. Expands RL action coverage from 2 to 13 actions (standard_offer, upsell, empathy_first, offer_discount, scarcity, deny_loan, collect_debt, teach, identity_answer, and others). Applies P1–P5 quality passes: regex fixes for banned phrases, system language leaks, wrong game mechanics, price format contamination, and decimal hallucination patterns.

**Outputs:** 3,110 clean training samples after filtering ~16.5% contaminated samples from 5,760 generated.

---

### 04A — Training Data Cleanup
`04PartA_training_data_Cleanup.ipynb`

Systematic quality audit of the generated dataset. Identifies and removes homogeneous opening patterns, system prompt leakage, out-of-character responses, and game mechanic errors. Applies find-and-replace at scale while preserving dataset diversity.

**Outputs:** Cleaned dataset with documented fix log per quality pass.

---

### 04B — Numeric Authority Fix
`04PartB_Numeric_Authority_Fix.ipynb`

Targeted fix for hallucinated numeric values in training samples — a key cause of price hallucination in deployed dialogue. Implements the NUMERIC AUTHORITY system prompt rules and applies 22-pattern phantom token filters. Reduces hallucination rate from ~20% to 6.7% in final evaluation.

**Outputs:** Numerically validated dataset; hallucination pattern catalogue.

---

### 05 — Qwen2.5 LoRA Fine-Tuning
`05v2_Qwen25_LoRA_Finetuning.ipynb`

QLoRA fine-tuning of Qwen2.5-7B-Instruct on the cleaned 3,110-sample dataset. Documents migration rationale from Mistral-7B (sales mode collapse, 79.9% multi-turn repetition rate, training-inference alignment failure). Configures LoRA rank, learning rate, and training epochs for Modal.com GPU execution.

**Outputs:** Fine-tuned adapter weights; training loss curves; checkpoint management.

---

### 06 — Model Evaluation
`06v2_Qwen_Model_Testing.ipynb`

Comprehensive evaluation of the fine-tuned Qwen v2 model. Tests single-turn pass rate, multi-turn coherence, hallucination rate, latency (P50/P95/P99), and RL compliance. Includes adversarial test cases across five hallucination types.

**Key Results:**
- Single-turn pass rate: 90% (18/20)
- RL compliance rate: 93.8% (30/32)
- Hallucination rate: 6.7%
- Latency: P50 1.33s / P95 1.97s / P99 2.18s

---

### 07 — FastAPI Backend (Production)
`07v5_FastAPI_Backend_Production.ipynb`

Documents the production FastAPI backend deployed on Railway. Covers the `/chat`, `/outcome`, and `/rl/export` endpoints, Redis-backed session state, RL feedback loop integration, and the separation-of-concerns architecture — game engine handles facts and pricing, RL agent makes strategic decisions, LLM handles dialogue delivery.

**Outputs:** Production API specification; endpoint documentation.

---

### 08A — Blockchain Smart Contract Development
`08a_Blockchain_Smart_Contract_Development.ipynb`

Development and testing of two ERC-721 smart contracts on Polygon Amoy testnet: `NPCMemory` (stores player interaction history on-chain) and `NPCAssetSystem` (verifies item ownership). Demonstrates blockchain-verified NPC memory as a solution to NPC amnesia across sessions.

**Outputs:** Deployed contract ABIs; Amoy testnet addresses; gas cost benchmarks.

---

### 08B — Blockchain Deployment and Memory Proof
`08b_Blockchain_Deployment_and_Memory_Proof.ipynb`

End-to-end proof of blockchain memory persistence. Simulates player sessions, writes interaction records to chain, and retrieves them across separate sessions — verifying that Whisper maintains auditable, tamper-proof player history. Documents gas costs per interaction.

**Outputs:** On-chain memory proof; cross-session retrieval verification; cost-per-interaction analysis.

---

### 12 — Survey Results Analysis
`12v3_Survey_Results_Analysis_v3.ipynb`

Statistical analysis of the within-subjects user study (n=15). Covers Wilcoxon signed-rank tests for engagement metrics, paired t-tests for trust scores (H2), and purchase behaviour analysis across Alpha vs Beta conditions. Computes Cohen's d effect sizes and generates all figures reported in Chapter 5.

**Key Results:**
- Session duration: Wilcoxon W=120, p<.001, Cohen's d=1.33 (H1 supported)
- Trust scores: t(14)=0.49, p=.629 (H2 not supported)
- Total purchases: 92 across 15 participants, 93% participation rate

---

### P7 — Numeric Linter
`P7_numeric_linter.py`

Utility script for auditing numeric consistency across training samples and thesis text. Flags price values that do not match the game's item price list, decimal format violations, and phantom token patterns. Used during the P4–P5 data quality passes.

---

## System Architecture

```
Player Input
     │
     ▼
React Frontend (Vercel)
     │
     ▼
FastAPI Backend (Railway) ──── Redis (Session State)
     │                │
     ▼                ▼
Qwen2.5-7B       RL Bandit Agent
(Modal.com)      (4 decision bandits)
                      │
                      ▼
            Polygon Amoy Testnet
            (NPCMemory + NPCAssetSystem)
```

---

## Infrastructure

| Component | Technology | Platform |
|---|---|---|
| Language Model | Qwen2.5-7B-Instruct + QLoRA | Modal.com |
| Backend API | FastAPI + Redis | Railway |
| Frontend | React | Vercel |
| Blockchain | ERC-721 smart contracts | Polygon Amoy Testnet |
| Training | QLoRA (rank 16, alpha 32) | Modal.com A100 |

---

## Key Findings

- **H1 (Engagement):** Supported. Beta NPC produced significantly longer sessions and higher purchase frequency vs Alpha (p<.001, Cohen's d=1.33).
- **H2 (Trust):** Not supported. No significant difference in perceived trust between AI and button-based conditions.
- **H3 (Economic Behaviour):** Partially supported. RL agent demonstrated adaptive discount and urgency strategies with 93.8% compliance rate, but emergent trading patterns were limited by study duration.
- **RQ4 (Architecture):** A minimum viable game-aware NPC architecture requires LLM + RL + blockchain integration; blockchain gas costs remained under $0.01 per interaction throughout the study.

---

## Citation

> Krishnan, R. (2026). *Game-Aware NPC: Player Based NPC Behavior Generation for Blockchain Gaming.* MSc Dissertation, Liverpool John Moores University.
