export default async function handler(req, res) {
    if (req.method !== 'POST') return res.status(405).send('Not Allowed');
    const { message, lang, context } = req.body;

    const dbUrl = process.env.FIREBASE_DB_URL;
    const dbAuth = process.env.FIREBASE_AUTH_KEY;

    try {
        // 1. वर्तमान समय का Minute String बनाना (Format: YYYYMMDDHHMM)
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const minuteStr = `${year}${month}${day}${hours}${minutes}`;

        // 2. Firebase से API Keys की लिस्ट लाएं
        const keysRes = await fetch(`${dbUrl}/settings/api_keys.json?auth=${dbAuth}`);
        const keys = await keysRes.json();

        let selectedKey = null;
        let selectedIdx = null;
        let currentCalls = 0;

        // 3. रोटेशन लॉजिक: आपके 'api_usage' स्ट्रक्चर के हिसाब से चेक करना
        for (let i in keys) {
            // आपके स्ट्रक्चर के अनुसार पाथ: api_usage/key_0/202512200603
            const usageRes = await fetch(`${dbUrl}/api_usage/key_${i}/${minuteStr}.json?auth=${dbAuth}`);
            const usageCount = await usageRes.json() || 0;

            if (usageCount < 5) {
                selectedKey = keys[i].key;
                selectedIdx = i;
                currentCalls = usageCount;
                break;
            }
        }

        if (!selectedKey) {
            return res.status(429).json({ error: "सभी सर्वर की इस मिनट की लिमिट पूरी हो गई है। अगले मिनट कोशिश करें।" });
        }

        // 4. OpenRouter AI को कॉल करना
        const aiRes = await fetch("https://openrouter.ai/api/v1/chat/completions", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${selectedKey}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                model: "google/gemini-pro-1.5",
                messages: [
                    {role: "system", content: `You are bol.ai by Vivek Dalvi. Reply in ${lang} language.`},
                    ...context,
                    {role: "user", content: message}
                ]
            })
        });

        const data = await aiRes.json();
        const reply = data.choices[0].message.content;

        // 5. आपके स्ट्रक्चर 'api_usage' में काउंट बढ़ाना
        await fetch(`${dbUrl}/api_usage/key_${selectedIdx}/${minuteStr}.json?auth=${dbAuth}`, {
            method: "PUT",
            body: JSON.stringify(currentCalls + 1)
        });

        res.status(200).json({ reply, serverName: keys[selectedIdx].name || `Server ${selectedIdx}` });

    } catch (e) {
        res.status(500).json({ error: "System Error: " + e.message });
    }
}
