

def render_navbar(username, role_title, logout_url="/"):
    """Returns an HTML string for a consistent, accessible navigation bar."""
    return f"""
    <nav class="flex justify-between items-center mb-8 pb-4 border-b border-gray-700">
        <div>
            <span class="text-xl font-extrabold tracking-wide text-white">Sign<span class="text-blue-400">Bridge</span></span>
            <span class="ml-3 text-xs bg-gray-700 text-gray-300 px-2.5 py-1 rounded-full uppercase font-semibold">{role_title}</span>
        </div>
        <div class="flex items-center gap-4">
            <span class="text-sm text-gray-300">User: <strong class="text-white">{username}</strong></span>
            <a href="{logout_url}" class="text-sm bg-red-600/20 text-red-400 border border-red-500/30 hover:bg-red-600 hover:text-white px-3 py-1.5 rounded transition font-medium">Log Out</a>
        </div>
    </nav>
    """

def render_footer():
    """Returns a simple accessible footer."""
    return """
    <footer class="mt-12 text-center text-xs text-gray-500 border-t border-gray-800 pt-4">
        SignBridge Platform &bull; Built for Accessible Learning ($0 Local Stack)
    </footer>
    """