"""Panggil inject_pwa() sekali di awal main_ui.py (setelah st.set_page_config)."""
import streamlit.components.v1 as components

_JS = """
<script>
(function () {
  const d = window.parent.document;
  const add = (tag, attrs) => {
    const key = attrs.rel || attrs.name;
    d.head.querySelectorAll(tag + '[data-diyos="' + key + '"]').forEach(n => n.remove());
    const el = d.createElement(tag);
    Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
    el.setAttribute('data-diyos', key);
    d.head.appendChild(el);
  };
  d.head.querySelectorAll('link[rel="manifest"]').forEach(n => n.remove());
  add('link', {rel: 'manifest', href: '/app/static/manifest.json'});
  add('link', {rel: 'apple-touch-icon', href: '/app/static/icon-192.png'});
  add('meta', {name: 'theme-color', content: '#EAB308'});
  add('meta', {name: 'description', content: 'Aplikasi AI pembuat ebook panduan pertukangan kayu dan kreasi DIY.'});
  if ('serviceWorker' in window.parent.navigator) {
    window.parent.navigator.serviceWorker
      .register('/app/static/sw.js', {scope: '/app/static/'})
      .catch(e => console.log('SW gagal:', e));
  }
})();
</script>
"""

def inject_pwa():
    components.html(_JS, height=0)
