"""Deaf portal page is rendered from templates/deaf_portal.html."""
'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SignBridge - Deaf Learner Portal</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-950 text-white min-h-screen p-6 md:p-12">
    <main class="max-w-3xl mx-auto bg-gray-900 p-8 rounded-2xl border border-gray-800 shadow-2xl">
        
        <!-- Navigation Header -->
        <nav class="flex justify-between items-center mb-8 pb-4 border-b border-gray-800">
            <div>
                <span class="text-xl font-black text-white">Sign<span class="text-purple-400">Bridge</span></span>
                <span class="ml-3 text-xs bg-purple-900/50 text-purple-300 border border-purple-700 px-3 py-1 rounded-full uppercase font-semibold">Deaf Mode</span>
            </div>
            <div class="flex items-center gap-4">
                <span class="text-sm text-gray-300">Welcome, <strong class="text-white">{{ username }}</strong></span>
                <a href="/" class="text-sm bg-gray-800 hover:bg-gray-700 text-gray-300 px-3 py-1.5 rounded-lg transition font-medium border border-gray-700">Log Out</a>
            </div>
        </nav>

        <!-- Topic Prompt Section -->
        <section class="mb-8">
            <h1 class="text-2xl font-bold text-purple-400 mb-2">Visual Learning Assistant</h1>
            <p class="text-gray-400 text-sm mb-6">Enter any learning subject below. The local AI will output a well-structured text breakdown featuring definitions, key headers, and summaries.</p>

            <form action="/deaf-dashboard" method="POST" class="space-y-4">
                <input type="hidden" name="username" value="{{ username }}">
                <div>
                    <label class="block text-xs font-semibold uppercase tracking-wider text-gray-300 mb-2">What topic do you want to explore?</label>
                    <input type="text" name="topic" required placeholder="e.g., Quantum Physics, Solar System, Renaissance..." class="w-full p-4 bg-gray-800 rounded-xl border border-gray-700 text-white text-lg focus:outline-none focus:border-purple-500 transition">
                </div>
                <button type="submit" class="w-full bg-purple-600 hover:bg-purple-500 p-4 rounded-xl font-bold text-lg transition shadow-lg shadow-purple-600/20">Generate Visual Module</button>
            </form>
        </section>

        <!-- Output Lesson Section -->
        {% if lesson %}
        <section class="mt-8 p-6 bg-gray-800/60 rounded-xl border border-gray-700">
            <h2 class="text-xl font-bold text-purple-300 mb-4 pb-3 border-b border-gray-700 flex items-center gap-2">
                📖 Module: {{ topic }}
            </h2>
            <div class="text-gray-100 text-base leading-relaxed whitespace-pre-line space-y-3 font-normal">
                {{ lesson }}
            </div>
        </section>
        {% endif %}

    </main>
</body>
</html>'''