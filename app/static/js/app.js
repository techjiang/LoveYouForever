/* LoveYouForever 前端交互
   保持零依赖：能用原生写的就不引库。
*/
(function () {
  'use strict';

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  /* ---------------- 移动端导航 ---------------- */
  var navToggle = $('#navToggle');
  var mainNav = $('#mainNav');
  if (navToggle && mainNav) {
    navToggle.addEventListener('click', function () {
      var open = mainNav.classList.toggle('open');
      navToggle.setAttribute('aria-expanded', String(open));
    });
    document.addEventListener('click', function (e) {
      if (!mainNav.contains(e.target) && !navToggle.contains(e.target)) {
        mainNav.classList.remove('open');
        navToggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  /* ---------------- 搜索面板 ---------------- */
  var searchToggle = $('#searchToggle');
  var searchPanel = $('#searchPanel');
  if (searchToggle && searchPanel) {
    searchToggle.addEventListener('click', function () {
      searchPanel.hidden = !searchPanel.hidden;
      if (!searchPanel.hidden) {
        var input = $('#searchInput');
        if (input) input.focus();
      }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') searchPanel.hidden = true;
    });
  }

  /* ---------------- 明暗切换 ---------------- */
  var themeToggle = $('#themeToggle');
  var ROOT = document.documentElement;
  var stored = null;
  try { stored = localStorage.getItem('lyf-theme'); } catch (e) { /* 隐私模式 */ }
  if (stored) ROOT.setAttribute('data-theme', stored);
  if (themeToggle) {
    themeToggle.addEventListener('click', function () {
      var next = ROOT.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      ROOT.setAttribute('data-theme', next);
      try { localStorage.setItem('lyf-theme', next); } catch (e) {}
      var meta = document.querySelector('meta[name="theme-color"]');
      if (meta) meta.setAttribute('content', next === 'dark' ? '#17121a' : '#fff8fa');
    });
  }

  /* ---------------- 页头滚动收缩 ---------------- */
  var header = $('#siteHeader');
  var backTop = $('#backTop');
  var lastY = 0;
  function onScroll() {
    var y = window.scrollY;
    if (header) header.classList.toggle('scrolled', y > 20);
    if (backTop) backTop.hidden = y < 400;
    lastY = y;
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
  if (backTop) backTop.addEventListener('click', function () {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  /* ---------------- Flash 自动消失 ---------------- */
  $$('.flash').forEach(function (el) {
    setTimeout(function () {
      el.style.transition = 'opacity .4s, transform .4s';
      el.style.opacity = '0';
      el.style.transform = 'translateX(20px)';
      setTimeout(function () { el.remove(); }, 400);
    }, 4200);
  });

  /* ---------------- 瞬间点赞 ---------------- */
  $$('.like-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var id = btn.getAttribute('data-moment');
      var token = (document.querySelector('input[name="csrf_token"]') || {}).value || '';
      btn.disabled = true;
      fetch('/moments/' + id + '/like', {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': token },
        credentials: 'same-origin'
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data.ok) return;
          btn.classList.toggle('liked', data.liked);
          var counter = btn.querySelector('.like-count');
          if (counter) counter.textContent = data.count;
        })
        .catch(function () {})
        .finally(function () { btn.disabled = false; });
    });
  });

  /* ---------------- 图片灯箱（自己写，不引库） ---------------- */
  var lightbox = null;
  function openLightbox(src, caption) {
    closeLightbox();
    lightbox = document.createElement('div');
    lightbox.className = 'lyf-lightbox';
    lightbox.innerHTML =
      '<div class="lb-backdrop"></div>' +
      '<figure class="lb-figure"><img src="' + src + '" alt="">' +
      (caption ? '<figcaption>' + caption + '</figcaption>' : '') +
      '</figure>' +
      '<button class="lb-close" aria-label="关闭">✕</button>';
    document.body.appendChild(lightbox);
    document.body.style.overflow = 'hidden';
    lightbox.querySelector('.lb-backdrop').addEventListener('click', closeLightbox);
    lightbox.querySelector('.lb-close').addEventListener('click', closeLightbox);
  }
  function closeLightbox() {
    if (lightbox) {
      lightbox.remove();
      lightbox = null;
      document.body.style.overflow = '';
    }
  }
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeLightbox(); });

  $$('[data-lightbox]').forEach(function (link) {
    link.addEventListener('click', function (e) {
      e.preventDefault();
      var img = link.querySelector('img');
      openLightbox(link.getAttribute('href'), img ? img.alt : '');
    });
  });
  // 文章正文里的图片也能点开
  $$('.post-body img.lyf-img').forEach(function (img) {
    img.style.cursor = 'zoom-in';
    img.addEventListener('click', function () { openLightbox(img.src, img.alt); });
  });

  /* ---------------- 上传组件 ---------------- */
  $$('[data-upload]').forEach(function (box) {
    var input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.multiple = box.hasAttribute('data-multiple');
    input.hidden = true;
    box.appendChild(input);

    var targetId = box.getAttribute('data-target');
    var list = targetId ? document.getElementById(targetId) : null;

    box.addEventListener('click', function (e) {
      if (e.target.tagName !== 'INPUT') input.click();
    });

    input.addEventListener('change', function () {
      Array.prototype.forEach.call(input.files, function (file) {
        uploadOne(file, box, list);
      });
      input.value = '';
    });

    // 拖拽上传
    box.addEventListener('dragover', function (e) { e.preventDefault(); box.classList.add('dragging'); });
    box.addEventListener('dragleave', function () { box.classList.remove('dragging'); });
    box.addEventListener('drop', function (e) {
      e.preventDefault();
      box.classList.remove('dragging');
      Array.prototype.forEach.call(e.dataTransfer.files, function (file) { uploadOne(file, box, list); });
    });
  });

  function uploadOne(file, box, list) {
    var form = new FormData();
    form.append('file', file);
    form.append('category', box.getAttribute('data-category') || 'covers');
    var tokenInput = document.querySelector('input[name="csrf_token"]');
    if (tokenInput) form.append('csrf_token', tokenInput.value);

    var progress = document.createElement('span');
    progress.className = 'upload-progress';
    progress.textContent = '上传中…';
    box.appendChild(progress);

    var handler = box.getAttribute('data-callback');
    fetch('/upload', { method: 'POST', body: form, credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        progress.remove();
        if (!data.ok) {
          alert(data.message || '上传失败');
          return;
        }
        if (list) {
          var item = document.createElement('div');
          item.className = 'upload-item';
          item.innerHTML = '<img src="' + data.url + '" alt=""><input type="hidden" name="' +
            (box.getAttribute('data-field') || 'images') + '" value="' + data.url + '">' +
            '<button type="button" class="upload-del">✕</button>';
          item.querySelector('.upload-del').addEventListener('click', function () { item.remove(); });
          list.appendChild(item);
        }
        if (handler && typeof window[handler] === 'function') {
          window[handler](data.url);
        }
        box.dispatchEvent(new CustomEvent('lyf:uploaded', { detail: data }));
      })
      .catch(function () { progress.remove(); alert('上传失败，请重试'); });
  }

  /* ---------------- Markdown 实时预览 ---------------- */
  var mdInput = $('#contentMd');
  var mdPreview = $('#mdPreview');
  if (mdInput && mdPreview) {
    var timer = null;
    mdInput.addEventListener('input', function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        var body = mdInput.value;
        var tokenInput = document.querySelector('input[name="csrf_token"]');
        fetch('/admin/preview', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': tokenInput ? tokenInput.value : '' },
          credentials: 'same-origin',
          body: JSON.stringify({ content: body })
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            mdPreview.innerHTML = data.html;
            var minutes = $('#readingMinutes');
            if (minutes) minutes.textContent = data.minutes;
          })
          .catch(function () {});
      }, 420);
    });
  }

  /* ---------------- 在一起计时（插件挂件） ---------------- */
  var counterEl = document.querySelector('.lyf-plugin-love-counter');
  if (counterEl) {
    var boundAt = new Date(counterEl.getAttribute('data-bound') || Date.now());
    var clock = counterEl.querySelector('.lc-clock');
    setInterval(function () {
      var diff = Math.max(Date.now() - boundAt.getTime(), 0);
      var d = Math.floor(diff / 86400000);
      var h = Math.floor((diff % 86400000) / 3600000);
      var m = Math.floor((diff % 3600000) / 60000);
      if (clock) clock.textContent = '相爱 ' + d + ' 天 ' + h + ' 小时 ' + m + ' 分';
    }, 30000);
  }

  /* ---------------- 彩蛋：连击爱心 ---------------- */
  var clicks = 0;
  var clickTimer = null;
  var brandLogo = document.querySelector('.footer-logo');
  if (brandLogo) {
    brandLogo.addEventListener('click', function () {
      clicks++;
      clearTimeout(clickTimer);
      clickTimer = setTimeout(function () { clicks = 0; }, 1200);
      if (clicks >= 5) {
        clicks = 0;
        burstHearts();
      }
    });
  }

  function burstHearts() {
    for (var i = 0; i < 24; i++) {
      (function (i) {
        setTimeout(function () {
          var heart = document.createElement('span');
          heart.textContent = ['❤', '💕', '💗', '💖'][i % 4];
          heart.style.cssText =
            'position:fixed;left:' + (Math.random() * 100) + 'vw;bottom:-40px;font-size:' +
            (14 + Math.random() * 22) + 'px;z-index:9999;pointer-events:none;transition:transform 2.6s linear,opacity 2.6s;';
          document.body.appendChild(heart);
          requestAnimationFrame(function () {
            heart.style.transform = 'translateY(-' + (window.innerHeight + 80) + 'px) rotate(' + (Math.random() * 60 - 30) + 'deg)';
            heart.style.opacity = '0';
          });
          setTimeout(function () { heart.remove(); }, 2800);
        }, i * 55);
      })(i);
    }
  }
  window.lyfBurstHearts = burstHearts;

  /* ---------------- 相对时间刷新 ---------------- */
  $$('time[data-relative]').forEach(function (el) {
    var iso = el.getAttribute('datetime');
    if (!iso) return;
    var diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60) el.textContent = '刚刚';
    else if (diff < 3600) el.textContent = Math.floor(diff / 60) + ' 分钟前';
    else if (diff < 86400) el.textContent = Math.floor(diff / 3600) + ' 小时前';
  });
})();
