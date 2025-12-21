export default async function handler(req, res) {
    if (req.method !== 'POST') return res.status(405).send('Not Allowed');
    const { message, lang, context } = req.body;

    const dbUrl = process.env.FIREBASE_DB_URL;
    const dbAuth = process.env.FIREBASE_AUTH_KEY;

    try {
        // 1. डेटा फेच करें
        const keysRes = await fetch(`${dbUrl}/settings/api_keys.json?auth=${dbAuth}`);
        const keys = await keysRes.json();

        // अगर डेटाबेस से कुछ नहीं मिला
        if (!keys) {
            return res.status(500).json({ error: "Firebase से API Keys नहीं मिल पाईं। अपना Auth Key और URL चेक करें।" });
        }

        // 2. वर्तमान मिनट का स्ट्रिंग (Timestamp logic)
        const minuteStr = new Date().toISOString().substring(0, 16).replace(/[^0-9]/g, "");

        let selectedKey = null;
        let selectedIdx = null;

        // 3. रोटेशन लॉजिक
        for (let i in keys) {
            if (!keys[i]) continue; // अगर कोई इंडेक्स खाली है तो छोड़ दें

            const usageRes = await fetch(`${dbUrl}/api_usage/key_${i}/${minuteStr}.json?auth=${dbAuth}`);
            const usageCount = await usageRes.json() || 0;

            if (usageCount < 5) {
                selectedKey = keys[i].key;
                selectedIdx = i;
                break;
            }
        }

        if (!selectedKey) return res.status(429).json({ error: "सभी सर्वर की लिमिट खत्म। 1 मिनट रुकें।" });

        // 4. AI Call
        const aiRes = await fetch("https://openrouter.ai/api/v1/chat/completions", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${selectedKey}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                model: "google/gemini-pro-1.5",
                messages: [
                    {role: "system", content: `You are bol.ai by Vivek Dalvi. Reply in ${lang}.`},
                    ...context,
                    {role: "user", content: message}
                ]
            })
        });

        const data = await aiRes.json();
        if(!data.choices) throw new Error("AI Response Error");

        const reply = data.choices[0].message.content;

        // 5. काउंटर अपडेट
        await fetch(`${dbUrl}/api_usage/key_${selectedIdx}/${minuteStr}.json?auth=${dbAuth}`, {
            method: "PUT",
            body: "5" // या रीयल काउंटर बढ़ाएं, टेस्टिंग के लिए 5 भी रख सकते हैं
        });

        res.status(200).json({ reply, serverName: keys[selectedIdx].name || "Server" });

    } catch (e) {
        res.status(500).json({ error: "Backend Error: " + e.message });
    }
}
