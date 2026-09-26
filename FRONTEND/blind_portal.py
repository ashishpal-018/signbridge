"""Blind portal page is rendered from templates/blind_portal.html."""
'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SignBridge - Blind Learner Portal</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        function speakText(text) {
            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
                let utterance = new SpeechSynthesisUtterance(text);
                utterance.rate = 1.0; // Normal speed
                window.speechSynthesis.speak(utterance);
            } else {
                alert("Speech synthesis is not supported on your browser.");
            }
        }
        function stopSpeech() {
            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
            }
        }
    </script>
</head>
<body class="bg-gray-950 text-white min-h-screen p-6 md:p-12">
    <main class="max-w-3xl mx-auto bg-gray-900 p-8 rounded-2xl border border-gray-800 shadow-2xl">
        
        <!-- Navigation Header -->
        <nav class="flex justify-between items-center mb-8 pb-4 border-b border-gray-800">
            <div>
                <span class="text-xl font-black text-white">Sign<span class="text-blue-400">Bridge</span></span>
                <span class="ml-3 text-xs bg-blue-900/50 text-blue-300 border border-blue-700 px-3 py-1 rounded-full uppercase font-semibold">Blind Mode</span>
            </div>
            <div class="flex items-center gap-4">
                <span class="text-sm text-gray-300">Welcome, <strong class="text-white">{{ username }}</strong></span>
                <a href="/" class="text-sm bg-gray-800 hover:bg-gray-700 text-gray-300 px-3 py-1.5 rounded-lg transition font-medium border border-gray-700">Log Out</a>
            </div>
        </nav>

        <!-- Topic Prompt Section -->
        <section class="mb-8">
            <h1 class="text-2xl font-bold text-blue-400 mb-2">Audio Learning Assistant</h1>
            <p class="text-gray-400 text-sm mb-6">Type any topic you wish to study. The local AI will generate a concise lesson optimized for audio narration.</p>

            <form action="/blind-dashboard" method="POST" class="space-y-4">
                <input type="hidden" name="username" value="{{ username }}">
                <div>
                    <label class="block text-xs font-semibold uppercase tracking-wider text-gray-300 mb-2">What topic do you want to explore?</label>
                    <input type="text" name="topic" required placeholder="e.g., Photosynthesis, World War II, Gravity..." class="w-full p-4 bg-gray-800 rounded-xl border border-gray-700 text-white text-lg focus:outline-none focus:border-blue-500 transition">
                </div>
                <button type="submit" class="w-full bg-blue-600 hover:bg-blue-500 p-4 rounded-xl font-bold text-lg transition shadow-lg shadow-blue-600/20">Generate Audio Lesson</button>
            </form>
        </section>

        <!-- Output Lesson Section -->
        {% if lesson %}
        <section class="mt-8 p-6 bg-gray-800/60 rounded-xl border border-gray-700">
            <div class="flex flex-wrap justify-between items-center gap-4 mb-4 pb-3 border-b border-gray-700">
                <h2 class="text-lg font-bold text-emerald-400">Lesson Topic: {{ topic }}</h2>
                <div class="flex gap-2">
                    <button onclick="speakText(`{{ lesson }}`)" class="bg-emerald-600 hover:bg-emerald-500 px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition shadow-md">
                        🔊 Read Aloud
                    </button>
                    <button onclick="stopSpeech()" class="bg-red-600/20 hover:bg-red-600 text-red-300 hover:text-white border border-red-500/30 px-3 py-2 rounded-lg text-sm font-bold transition">
                        ⏹ Stop
                    </button>
                </div>
            </div>
            <div class="text-gray-100 text-lg leading-relaxed whitespace-pre-line font-light">
                {{ lesson }}
            </div>
        </section>
        {% endif %}

    </main>
</body>
</html>'''