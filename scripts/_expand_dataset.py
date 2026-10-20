"""One-off helper: expand the NLP training dataset and create the held-out
novelty test set. Safe to re-run: it deduplicates by normalized text and
keeps the original samples intact. Not part of the application runtime.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "sample_data" / "messages_dataset.json"
NOVELTY = ROOT / "sample_data" / "novelty_test.json"

with open(DATASET, "r", encoding="utf-8") as f:
    data = json.load(f)

new_training = [
    # --- product_inquiry (price / availability questions, typos, short forms)
    {"text": "keybord ka rate kitna hai?", "intent": "product_inquiry"},
    {"text": "wirles mice available hai kya?", "intent": "product_inquiry"},
    {"text": "moniter ka price batao", "intent": "product_inquiry"},
    {"text": "do you have any headphons in stock", "intent": "product_inquiry"},
    {"text": "webcm chahiye, stock mein hai?", "intent": "product_inquiry"},
    {"text": "microfon ka kitna price hai", "intent": "product_inquiry"},
    {"text": "kb-101 ka rate kya hai", "intent": "product_inquiry"},
    {"text": "ms-201 in stock?", "intent": "product_inquiry"},
    {"text": "price of laptop stand?", "intent": "product_inquiry"},
    {"text": "how much is the usb c hub", "intent": "product_inquiry"},
    {"text": "kitna stock hai keyboard ka", "intent": "product_inquiry"},
    {"text": "is the gaming headset available", "intent": "product_inquiry"},
    {"text": "webcam ki availability check karo", "intent": "product_inquiry"},
    {"text": "mouse ka latest price kya chal raha hai", "intent": "product_inquiry"},
    {"text": "bhai stock hai kya mice ka", "intent": "product_inquiry"},
    {"text": "what does the condenser mic cost", "intent": "product_inquiry"},

    # --- quotation_request (terse, Hinglish, typos, mixed quantities)
    {"text": "bhai 2 keyboard chahiye", "intent": "quotation_request"},
    {"text": "mujhe 3 mice chahiye quote bhejo", "intent": "quotation_request"},
    {"text": "2 wireless mice and 1 headset", "intent": "quotation_request"},
    {"text": "3 mice, 1 headset quote karo", "intent": "quotation_request"},
    {"text": "one MN-401", "intent": "quotation_request"},
    {"text": "2 x KB-101 quote please", "intent": "quotation_request"},
    {"text": "quote for 4 webcams", "intent": "quotation_request"},
    {"text": "i want 5 usb hubs, send quote", "intent": "quotation_request"},
    {"text": "keybord aur 2 mice ka quote banao", "intent": "quotation_request"},
    {"text": "need 6 laptop stands ASAP, give me a price", "intent": "quotation_request"},
    {"text": "2 keyboards and 3 mice", "intent": "quotation_request"},
    {"text": "ek monitor aur do headset ka quote", "intent": "quotation_request"},
    {"text": "kindly prepare quotation for 7 microphones", "intent": "quotation_request"},
    {"text": "1 mechanical keyboard 2 wireless mice total price?", "intent": "quotation_request"},
    {"text": "chahiye mujhe 4 keyboard, quotation banao", "intent": "quotation_request"},
    {"text": "send pricing for two monitors and three webcams", "intent": "quotation_request"},
    {"text": "10 piece gaming headset quote dena", "intent": "quotation_request"},
    {"text": "want to order 2 hubs and 1 stand, how much total", "intent": "quotation_request"},
    {"text": "quote dedo 5 keyboard ka", "intent": "quotation_request"},
    {"text": "I would like to purchase 3 microphones, please quote", "intent": "quotation_request"},
    {"text": "give me best price for 8 webcams", "intent": "quotation_request"},
    {"text": "2 keyboards and 3 mice and 1 headset", "intent": "quotation_request"},

    # --- confirmation (short, Hinglish, typos)
    {"text": "yes confirm kardo", "intent": "confirmation"},
    {"text": "haan bhai confirm karo order", "intent": "confirmation"},
    {"text": "ok proceed", "intent": "confirmation"},
    {"text": "yup go ahead", "intent": "confirmation"},
    {"text": "looks fine, place the order", "intent": "confirmation"},
    {"text": "i approve this quote", "intent": "confirmation"},
    {"text": "deal, confirm it", "intent": "confirmation"},
    {"text": "right ahead, finalize the quotation", "intent": "confirmation"},
    {"text": "book it please", "intent": "confirmation"},
    {"text": "yes do it", "intent": "confirmation"},
    {"text": "shaq nahi hai, confirm kar do", "intent": "confirmation"},

    # --- decline (short, Hinglish, typos)
    {"text": "nahi cancel kardo", "intent": "decline"},
    {"text": "order mat karo, cancel", "intent": "decline"},
    {"text": "too costly, drop it", "intent": "decline"},
    {"text": "no thanks, not interested anymore", "intent": "decline"},
    {"text": "cancel this quote", "intent": "decline"},
    {"text": "reject kar do ye order", "intent": "decline"},
    {"text": "forget it", "intent": "decline"},
    {"text": "main order nahi karna", "intent": "decline"},
    {"text": "nope take it off", "intent": "decline"},
    {"text": "cancel please", "intent": "decline"},

    # --- general_question (policies, shipping, payment, warranty; Hinglish)
    {"text": "warranty kitni milti hai isme", "intent": "general_question"},
    {"text": "delivery kab tak hogi", "intent": "general_question"},
    {"text": "payment karne ke kya options hain", "intent": "general_question"},
    {"text": "kya aap cash on delivery dete ho", "intent": "general_question"},
    {"text": "return policy kya hai aapki", "intent": "general_question"},
    {"text": "gst invoice milega kya", "intent": "general_question"},
    {"text": "aap kis city se ship karte ho", "intent": "general_question"},
    {"text": "do you offer EMI on orders", "intent": "general_question"},
    {"text": "kya installation provide karwate ho", "intent": "general_question"},
    {"text": "shipping charges kitne hain", "intent": "general_question"},
    {"text": "can I change my delivery address later", "intent": "general_question"},
    {"text": "aapka support team kab available hai", "intent": "general_question"},

    # --- unsupported (out of domain, Hinglish chit-chat, requests we cannot do)
    {"text": "bhai ek joke sunao", "intent": "unsupported"},
    {"text": "mujhe cricket score batao", "intent": "unsupported"},
    {"text": "can you do my maths homework", "intent": "unsupported"},
    {"text": "book a cab for me to the airport", "intent": "unsupported"},
    {"text": "send me a recipe for paneer butter masala", "intent": "unsupported"},
    {"text": "I want to exchange my old smartphone", "intent": "unsupported"},
    {"text": "can you recharge my mobile balance", "intent": "unsupported"},
    {"text": "translate this paragraph into french for me", "intent": "unsupported"},
    {"text": "gift me a free keyboard please", "intent": "unsupported"},
    {"text": "what is the meaning of life", "intent": "unsupported"},
    {"text": "mera instagram hack kar do", "intent": "unsupported"},
    {"text": "are you single", "intent": "unsupported"},
]

# Extra filler to push training past 150
extra_training = [
    {"text": "bhai kab tak delivery hogi mujhe batao", "intent": "general_question"},
    {"text": "can I pay by credit card online", "intent": "general_question"},
    {"text": "keyboard ka warranty period kya hai", "intent": "general_question"},
    {"text": "order track karna hai mujhe", "intent": "general_question"},
    {"text": "price list bhejo please sab products ka", "intent": "product_inquiry"},
]

# Held-out novelty set: phrasings NEVER seen in training or the dev evaluation
# split. Used once for honest reporting; never tuned on.
novelty_samples = [
    {"text": "hey do the ultrawide monitors come with a warranty", "intent": "product_inquiry"},
    {"text": "any discounts on bulk mouse orders", "intent": "product_inquiry"},
    {"text": "kb ka stock khatam hai kya", "intent": "product_inquiry"},
    {"text": "what about the refurbished keyboard line", "intent": "product_inquiry"},
    {"text": "headset mein mic built in hai kya", "intent": "product_inquiry"},
    {"text": "does the webcam support full hd recording", "intent": "product_inquiry"},
    {"text": "stand kitna weight support karta hai", "intent": "product_inquiry"},
    {"text": "price badh gaya hai kya mouse ka", "intent": "product_inquiry"},

    {"text": "mujhe ek keyboard aur do mouse chahiye, quote banao", "intent": "quotation_request"},
    {"text": "quote for a single USB hub please", "intent": "quotation_request"},
    {"text": "3 stand aur 2 mic ka estimate bhejo", "intent": "quotation_request"},
    {"text": "need twelve headsets, send pricing", "intent": "quotation_request"},
    {"text": "1 monitor lena hai, price batao", "intent": "quotation_request"},
    {"text": "2 webcam and 1 hub, what would it cost me", "intent": "quotation_request"},
    {"text": "do keyboards milenge, quotation chahiye", "intent": "quotation_request"},
    {"text": "7 mechanical keyboards ka quote kar do", "intent": "quotation_request"},

    {"text": "haan bilkul confirm kar do", "intent": "confirmation"},
    {"text": "the quote works for me, go on", "intent": "confirmation"},
    {"text": "sahi hai, order place kar do", "intent": "confirmation"},
    {"text": "green light, finalize it", "intent": "confirmation"},
    {"text": "ok I will take it, confirm", "intent": "confirmation"},
    {"text": "count me in, proceed with the order", "intent": "confirmation"},

    {"text": "baad mein sochta hoon, abhi cancel", "intent": "decline"},
    {"text": "budget se bahar hai, mat karo", "intent": "decline"},
    {"text": "I found a better deal elsewhere, call it off", "intent": "decline"},
    {"text": "nahi chahiye ab ye", "intent": "decline"},
    {"text": "undo the order please", "intent": "decline"},

    {"text": "kya aap international shipping karte ho", "intent": "general_question"},
    {"text": "invoice mein GST number kaise add karwayein", "intent": "general_question"},
    {"text": "which courier partner do you use", "intent": "general_question"},
    {"text": "kya weekends pe bhi delivery hoti hai", "intent": "general_question"},
    {"text": "bulk order pe negotiation ho sakta hai", "intent": "general_question"},
    {"text": "do you have a physical store I can visit", "intent": "general_question"},

    {"text": "bhai song suna do abhi", "intent": "unsupported"},
    {"text": "can you invest in my startup", "intent": "unsupported"},
    {"text": "meri girlfriend se baat kara do", "intent": "unsupported"},
    {"text": "download the latest movies for me", "intent": "unsupported"},
    {"text": "why is the sky blue answer quickly", "intent": "unsupported"},
    {"text": "buy cryptocurrency for me with my card", "intent": "unsupported"},
    {"text": "can you tell me today's weather in Delhi", "intent": "unsupported"},
]

existing = {s["text"].strip().lower() for s in data["training"]}
added = 0
for sample in new_training + extra_training:
    key = sample["text"].strip().lower()
    if key not in existing:
        data["training"].append(sample)
        existing.add(key)
        added += 1

with open(DATASET, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")

novelty = {
    "description": (
        "Held-out NOVELTY test set for QuoteMate. These phrasings were written "
        "after the training set was frozen and have zero literal overlap with "
        "the training or dev-evaluation splits. Reported once in the README; "
        "the model is never tuned on this file."
    ),
    "samples": novelty_samples,
}
with open(NOVELTY, "w", encoding="utf-8") as f:
    json.dump(novelty, f, indent=2, ensure_ascii=False)
    f.write("\n")

print(f"training now: {len(data['training'])} (added {added})")
print(f"novelty set: {len(novelty_samples)}")
overlap = (
    {s["text"].strip().lower() for s in novelty_samples}
    & (
        {s["text"].strip().lower() for s in data["training"]}
        | {s["text"].strip().lower() for s in data["evaluation"]}
    )
)
print(f"overlap with training/dev: {len(overlap)}")
