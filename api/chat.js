export default async function handler(req, res) {
    if (req.method !== 'POST') return res.status(405).send('Not Allowed');
    const { message } = req.body;

    // 1. Firebase से Keys की लिस्ट लेना
    const dbUrl = process.env.FIREBASE_DB_URL; 
    const dbSecret = process.env.FIREBASE_AUTH_KEY;
    
    const response = await fetch(`${dbUrl}/settings/api_keys.json?auth=${dbSecret}`);
    const keys = await response.json();

    // 2. वो चाबी ढूँढना जिसकी लिमिट (5) बची हो
    let selectedKey = null;
    let selectedIdx = null;

    for (let i in keys) {
        if (keys[i].calls < 5) {
            selectedKey = keys[i].key;
            selectedIdx = i;
            break;
        }
    }

    if (!selectedKey) return res.status(429).json({ reply: "सभी सर्वर व्यस्त हैं, 1 मिनट रुकें।" });

    try {
        // 3. AI (OpenRouter) को कॉल करना
        const aiRes = await fetch("https://openrouter.ai/api/v1/chat/completions", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${selectedKey}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                model: "google/gemini-pro-1.5",
                messages: [{ role: "user", content: message }]
            })
        });
        const data = await aiRes.json();
        const aiReply = data.choices[0].message.content;

        // 4. Firebase में 'calls' काउंट बढ़ाना
        await fetch(`${dbUrl}/settings/api_keys/${selectedIdx}/calls.json?auth=${dbSecret}`, {
            method: "PUT",
            body: JSON.stringify(keys[selectedIdx].calls + 1)
        });

        res.status(200).json({ reply: aiReply });
    } catch (e) {
        res.status(500).json({ error: "Server Error" });
    }
}
