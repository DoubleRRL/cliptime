# SupoClip Setup Guide (Baby Edition) 🍼

Since you've already got the repo cloned, let's get you running with **Ollama** and **Gemma**.

### 1. Check Your Ports 🔌
You mentioned staying active on ports. I've already checked, and **3000** (Frontend) and **8000** (Backend) are **CLEAR**. No conflicts!

### 2. Get Your Model Ready 🧠
For your **MacBook M2 Air**, we're using the latest **Gemma 4 E4B**. It's fast, uses very little battery, and has a huge brain for long videos.

Run this in your terminal:
```bash
ollama pull gemma4:e4b
```

### 3. The "Secret Sauce" (.env file) 📝
I've already created a `.env` file for you in the project root. You just need to add your **AssemblyAI** key.

Open `.env` and look for this line:
```env
ASSEMBLY_AI_API_KEY=your_key_here
```
Replace `your_key_here` with your actual key from [AssemblyAI](https://www.assemblyai.com/).

> [!IMPORTANT]
> I've already pointed the app to your Mac's Ollama using `http://host.docker.internal:11434/v1`. This is the "magic" that lets Docker see your models.

### 4. Fire It Up! 🚀
Since you want to save tokens and keep things simple, just use the start script:

```bash
chmod +x start.sh
./start.sh
```

### 5. How to tell it's working
1.  **Frontend**: Open [http://localhost:3000](http://localhost:3000)
2.  **Backend Docs**: Open [http://localhost:8000/docs](http://localhost:8000/docs)
3.  **Logs**: If things feel slow, run `docker-compose logs -f worker` to see the AI thinking.

### Summary of "Token Saving"
- **LLM**: Using Ollama means **$0** cost for the "thinking" part.
- **Transcription**: AssemblyAI has a generous free tier, so you won't burn cash unless you're processing hours of video.

---
**Need help with the AssemblyAI key or something else? Just ask!**
