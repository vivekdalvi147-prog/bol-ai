export default async function handler(req, res) {
    if (req.method !== 'POST') return res.status(405).send('Not Allowed');
    
    // Environment Variables को लोड करें
    const dbUrl = process.env.FIREBASE_DB_URL;
    const dbAuth = process.env.FIREBASE_AUTH_KEY;

    // चेक करें कि क्या Variables मौजूद हैं
    if (!dbUrl || !dbAuth) {
        console.error("Missing Env Variables: Check Vercel Settings");
        return res.status(500).json({ error: "Environment Variables (URL or Auth) missing in Vercel" });
    }

    try {
        const { message, lang, context } = req.body;

        // 1. Firebase से डेटा माँगना
        const fetchUrl = `${dbUrl.replace(/\/$/, '')}/settings/api_keys.json?auth=${dbAuth}`;
        const response = await fetch(fetchUrl);
        
        if (!response.ok) {
            const errText = await response.text();
            console.error("Firebase Fetch Error:", errText);
            return res.status(500).json({ error: "Firebase Permission Denied. Check your Auth Key." });
        }

        const keys = await response.json();

        if (!keys) {
            console.error("No keys found at path: settings/api_keys");
            return res.status(500).json({ error: "No API Keys found in Firebase Database" });
        }

        // 2. रोटेशन लॉजिक (Timestamp आधारित)
        const minuteStr = new Date().toISOString().substring(0, 16).replace(/[^0-9]/g, "");
        let selectedKey = null;
        let selectedIdx = null;

        // Keys को Loop करना (इंडेक्स 0 से शुरू)
        const keysArray = Object.keys(keys);
        for (let i of keysArray) {
            if (!keys[i] || !keys[i].key) continue;

            // Usage चेक करें
            const usageUrl = `${dbUrl.replace(/\/$/, '')}/api_usage/key_${i}/${minuteStr}.json?auth=${dbAuth}`;
            const usageRes = await fetch(usageUrl);
            const usageCount = await usageRes.json() || 0;

            if (usageCount < 5) {
                selectedKey = keys[i].key;
                selectedIdx = i;
                break;
            }
        }

        if (!selectedKey) return res.status(429).json({ error: "All keys limit reached for this minute." });

        // 3. OpenRouter AI को कॉल करना
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
                    ...(context || []),
                    {role: "user", content: message}
                ]
            })
        });

        const data = await aiRes.json();
        
        if (!data.choices) {
            console.error("AI API Error:", data);
            return res.status(500).json({ error: "AI API Error. Check your OpenRouter Key/Credit." });
        }

        const reply = data.choices[0].message.content;

        // 4. काउंटर बढ़ाना
        await fetch(`${dbUrl.replace(/\/$/, '')}/api_usage/key_${selectedIdx}/${minuteStr}.json?auth=${dbAuth}`, {
            method: "PATCH",
            body: JSON.stringify({ calls: 5 }) // यहाँ आप मैन्युअली 5 कर रहे हैं टेस्टिंग के लिए
        });

        res.status(200).json({ reply, serverName: keys[selectedIdx].name || "Server" });

    } catch (e) {
        console.error("Critical Crash:", e.message);
        res.status(500).json({ error: "Internal Server Error: " + e.message });
    }
}
