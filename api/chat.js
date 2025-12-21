export default async function handler(req, res) {
    // 1. केवल POST रिक्वेस्ट की अनुमति दें
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method Not Allowed' });
    }

    try {
        const { message, lang, context } = req.body;
        const dbUrl = process.env.FIREBASE_DB_URL;
        const dbAuth = process.env.FIREBASE_AUTH_KEY;

        if (!dbUrl || !dbAuth) {
            throw new Error("Missing Environment Variables");
        }

        // 2. वर्तमान समय (Minute String) - रोटेशन के लिए
        const now = new Date();
        const minuteStr = now.toISOString().substring(0, 16).replace(/[^0-9]/g, "");

        // 3. Firebase से API Keys लाएं
        const keysRes = await fetch(`${dbUrl.replace(/\/$/, '')}/settings/api_keys.json?auth=${dbAuth}`);
        const keys = await keysRes.json();

        if (!keys) throw new Error("No API Keys found in Database");

        // 4. पहली खाली Key चुनें
        let selectedKey = null;
        let selectedIdx = null;

        for (let i in keys) {
            const usageRes = await fetch(`${dbUrl.replace(/\/$/, '')}/api_usage/key_${i}/${minuteStr}.json?auth=${dbAuth}`);
            const usage = await usageRes.json() || 0;
            if (usage < 5) {
                selectedKey = keys[i].key;
                selectedIdx = i;
                break;
            }
        }

        if (!selectedKey) return res.status(429).json({ error: "Server Busy. Wait 1 min." });

        // 5. OpenRouter AI को कॉल करें
        const aiRes = await fetch("https://openrouter.ai/api/v1/chat/completions", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${selectedKey}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                model: "google/gemini-flash-1.5",
                messages: [
                    { role: "system", content: `You are bol.ai by Vivek Dalvi. Reply in ${lang}.` },
                    ...(context || []),
                    { role: "user", content: message }
                ]
            })
        });

        const data = await aiRes.json();
        
        if (!data.choices) throw new Error(data.error?.message || "AI Error");

        // 6. काउंटर बढ़ाएं
        await fetch(`${dbUrl.replace(/\/$/, '')}/api_usage/key_${selectedIdx}/${minuteStr}.json?auth=${dbAuth}`, {
            method: "PUT",
            body: JSON.stringify(5) // रोटेशन के लिए इसे 5 सेट कर रहे हैं
        });

        return res.status(200).json({ 
            reply: data.choices[0].message.content, 
            serverName: keys[selectedIdx].name 
        });

    } catch (error) {
        console.error("Backend Error:", error.message);
        return res.status(500).json({ error: error.message });
    }
}
