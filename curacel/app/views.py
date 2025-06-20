import json
import requests
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from openai import OpenAI

from django.conf import settings
from openai import OpenAI

client = OpenAI(api_key=settings.OPENAI_API_KEY)
CURACEL_API_KEY = settings.OPENAI_API_KEY

def index(request):
    return render(request, "home.html")


@csrf_exempt
def claimgpt(request):
    if request.method == 'POST':
        user_input = request.POST.get('claim_description')
        attachment_url = request.POST.get('attachment_url')

        attachment_id = None

        # ✅ Step 1: Upload file from URL to Curacel
        if attachment_url:
            try:
                upload_response = requests.post(
                    url="https://api.playbox.grow.curacel.co/api/v1/attachments",
                    headers={"Authorization": f"Bearer {CURACEL_API_KEY}"},
                    json={"file_url": attachment_url}
                )
                upload_json = upload_response.json()

                # ✅ Accept 200 or 201 response, and extract attachment ID
                if upload_response.status_code in [200, 201] and "attachment" in upload_json:
                    attachment_id = upload_json["attachment"]["id"]
                else:
                    return JsonResponse({"error": "URL upload failed", "details": upload_json}, status=400)

            except Exception as e:
                return JsonResponse({"error": "Upload error", "details": str(e)}, status=500)

        attachments_list = [attachment_id] if attachment_id else []

        # ✅ Step 2: Generate structured JSON using GPT-4
        prompt = f"""
        Extract insurance claim data from the following description and return strictly valid JSON with these exact fields:

        - policy_number (string)
        - amount (integer, in NGN without ₦ or commas)
        - payment_details (object with keys: bank_name, account_number, sort_code — all strings)
        - child_partner_id (string or null)
        - attachments (list of integers – attachment IDs, use {attachments_list})

        Respond only with valid JSON (no explanation or markdown).

        Description: "{user_input}"
        """

        try:
            gpt_response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an insurance claims assistant."},
                    {"role": "user", "content": prompt}
                ]
            )
            claim_data = json.loads(gpt_response.choices[0].message.content)

            # Ensure attachment ID is injected if GPT skipped it
            if not claim_data.get("attachments"):
                claim_data["attachments"] = attachments_list

            # ✅ Step 3: Submit structured claim to Curacel
            claim_response = requests.post(
                url="https://api.playbox.grow.curacel.co/api/v1/claims",
                headers={
                    "Authorization": f"Bearer {CURACEL_API_KEY}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                json=claim_data
            )

            return JsonResponse(claim_response.json(), status=claim_response.status_code)

        except Exception as e:
            return JsonResponse({"error": "OpenAI or Curacel error", "details": str(e)}, status=500)

    return render(request, 'claimgpt.html')





@csrf_exempt
def policymatchgpt(request):
    if request.method == 'POST':
        user_input = request.POST.get('insurance_needs')

        # 🔍 Step 1: Extract query params with GPT
        extract_prompt = f"""
From the user's request, extract parameters for filtering insurance products via API.

Return valid JSON with these keys:
- type (string, one of: health, 3rd_party_auto, comprehensive_auto, life, marine, git, credit_life, fire_burglary, gadget, job_loss, personal_accident, micro_health, travel, investment_life, investment)
- cover_amount (float)
- age (int)
- beneficiaries (int)
- calculate_premium (int, must be 1)
- policy_start_date (string, YYYY-MM-DD)

Only respond with valid JSON.

User's request: "{user_input}"
"""

        try:
            param_response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You extract API query parameters from natural language."},
                    {"role": "user", "content": extract_prompt}
                ]
            )
            query_params = json.loads(param_response.choices[0].message.content)

        except Exception as e:
            return JsonResponse({"error": "GPT extraction failed", "details": str(e)}, status=500)

        # 🌐 Step 2: Call Curacel Products API with extracted filters
        try:
            product_res = requests.get(
                "https://api.playbox.grow.curacel.co/api/v1/products",
                headers={"Authorization": f"Bearer {CURACEL_API_KEY}"},
                params=query_params
            )
            products = product_res.json()

            if product_res.status_code != 200:
                return JsonResponse({"error": "Product API failed", "details": products}, status=400)

            # 🧠 Step 3: Slim product list before passing to GPT
            product_list = []
            for p in products.get("data", []):
                product_list.append({
                    "product_name": p.get("title"),
                    "product_code": p.get("code"),
                    "price": p.get("price"),
                    "type": p.get("product_type", {}).get("slug"),
                    "premium_frequency": p.get("premium_frequencies"),
                    "insurer": p.get("insurer", {}).get("name")
                })

            # 🧠 Step 4: GPT summarizes best match
            summary_prompt = f"""
Below is a list of insurance products that match the user's query.

Please recommend the **top 1 or 2** products and explain **briefly why** they are a good fit.

User Query: "{user_input}"

Products: {json.dumps(product_list)}

Respond with JSON like:
[
  {{
    "product_name": "...",
    "product_code": "...",
    "estimated_premium": "...",
    "why": "reason it's a good fit"
  }}
]
"""

            summary_response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You summarize and recommend insurance products."},
                    {"role": "user", "content": summary_prompt}
                ]
            )

            recommendation = json.loads(summary_response.choices[0].message.content)
            return JsonResponse({"match": recommendation})

        except Exception as e:
            return JsonResponse({"error": "GPT summarization or API failed", "details": str(e)}, status=500)

    return render(request, 'policy_match.html')

from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.http import JsonResponse
import requests
import json

# Replace this with your actual Curacel API Key

@csrf_exempt
def claims_assistant(request):
    if request.method == 'POST':
        claim_id = request.POST.get('claim_id')

        # Step 1: Fetch claim data from Curacel
        try:
            claim_res = requests.get(
                f"https://api.playbox.grow.curacel.co/api/v1/claims/{claim_id}",
                headers={
                    'Authorization':  f"Bearer {CURACEL_API_KEY}",
                    'Accept': 'application/json'
                }
            )
            claim_data = claim_res.json()

            if claim_res.status_code != 200:
                return JsonResponse({"error": "Failed to fetch claim", "details": claim_data}, status=400)

        except Exception as e:
            return JsonResponse({"error": "Claim fetch error", "details": str(e)}, status=500)

        # Step 2: Ask GPT to explain claim status
        try:
            gpt_prompt = f"""
            Here is an insurance claim record:
            {json.dumps(claim_data)}

            Please explain to the customer:
            - The current status of the claim
            - Whether it was approved or denied and why
            - If pending, what documents or steps are remaining
            - What they should do next

            Respond in simple, friendly language.
            """

            gpt_response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an insurance assistant that explains claim statuses to users."},
                    {"role": "user", "content": gpt_prompt}
                ]
            )

            explanation = gpt_response.choices[0].message.content

          
            return render(request, 'claim_assistance.html', {
"claim_id": claim_id,
                "status": claim_data.get("status"),
                "explanation": explanation
            })
        
        

        except Exception as e:
            return JsonResponse({"error": "GPT explanation failed", "details": str(e)}, status=500)

    return render(request, 'claim_assistance.html')




from django.shortcuts import render
from openai import OpenAI
import os

# Use environment variable or hardcode your key securely

def insurance_chatbot(request):
    user_input = ""
    response_text = ""

    if request.method == 'POST':
        user_input = request.POST.get('message')

        try:
            chat_completion = client.chat.completions.create(
                model="gpt-4",  # or "gpt-3.5-turbo"
                messages=[
                    {"role": "system", "content": "You are an expert insurance advisor. Answer clearly and concisely."},
                    {"role": "user", "content": user_input}
                ]
            )
            response_text = chat_completion.choices[0].message.content
        except Exception as e:
            response_text = f"Error: {str(e)}"

    return render(request, 'insurance_bot.html', {
        'user_input': user_input,
        'response': response_text
    })
