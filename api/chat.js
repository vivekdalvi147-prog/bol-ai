export default async function handler(req, res) {
    if (req.method !== 'POST') return res.status(405).json({ error: 'Method Not Allowed' });

    const dbUrl = process.env.FIREBASE_DB_URL;
    const dbAuth = process.env.FIREBASE_AUTH_KEY;

    try {
        // Firebase से डेटा फेच करें
        const response = await fetch(`${dbUrl.replace(/\/$/, '')}/settings.json?auth=${dbAuth}`);
        const settings = await response.json();

        // अगर यहाँ NULL आया, तो एरर दिखाएँ
        if (!settings || !settings.api_keys) {
            return res.status(500).json({ error: "Firebase Database is returning NULL. Check your URL and Secret Key in Vercel Settings." });
        }

        const keys = settings.api_keys;
        const { message, lang, context } = req.body;

        // मिनट रोटेशन लॉजिक
        const minuteStr = new Date().toISOString().substring(0, 16).replace(/[^0-9]/g, "");

        let selectedKey = null;
        let selectedIdx = null;

        for (let i in keys) {
            if (!keys[i] || !keys[i].key) continue;

            const usageRes = await fetch(`${dbUrl.replace(/\/$/, '')}/api_usage/key_${i}/${minuteStr}.json?auth=${dbAuth}`);
            const usage = await usageRes.json() || 0;

            if (usage < 5) {
                selectedKey = keys[i].key;
                selectedIdx = i;
                break;
            }
        }

        if (!selectedKey) return res.status(429).json({ error: "All servers busy for this minute." });

        // AI को कॉल करें
        const aiRes = await fetch("https://openrouter.ai/api/v1/chat/completions", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${selectedKey}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                model: "google/gemini-flash-1.5",
                messages: [
                    {role: "system", content: `You are bol.ai by Vivek Dalvi. Reply in ${lang}.`},
                    ...context,
                    {role: "user", content: message}
                ]
            })
        });

        const data = await aiRes.json();
        if (!data.choices) throw new Error(data.error?.message || "AI API Error");

        // इस्तेमाल बढ़ाएँ
        await fetch(`${dbUrl.replace(/\/$/, '')}/api_usage/key_${selectedIdx}/${minuteStr}.json?auth=${dbAuth}`, {
            method: "PUT",
            body: "5" // टेस्टिंग के लिए 5 सेट कर रहे हैं
        });

        res.status(200).json({ reply: data.choices[0].message.content, serverName: keys[selectedIdx].name });

    } catch (e) {
        res.status(500).json({ error: "Backend Crash: " + e.message });
    }
}
