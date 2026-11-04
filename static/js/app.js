(function () {
  'use strict';

  var nav = document.getElementById('app-nav');
  var toggle = document.getElementById('nav-toggle');
  var closeButton = document.getElementById('nav-close');
  var overlay = document.getElementById('nav-overlay');

  if (!nav || !toggle || !overlay) {
    return;
  }

  var isOpen = false;
  var lastFocused = null;
  var desktopQuery = window.matchMedia('(min-width: 48rem)');
  var focusableSelector = [
    'a[href]',
    'button:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])'
  ].join(',');

  function getFocusable() {
    return Array.prototype.filter.call(
      nav.querySelectorAll(focusableSelector),
      function (element) {
        return element.getClientRects().length > 0;
      }
    );
  }

  function openNav() {
    if (isOpen) {
      return;
    }

    isOpen = true;
    lastFocused = document.activeElement;
    nav.classList.add('is-open');
    toggle.setAttribute('aria-expanded', 'true');
    toggle.setAttribute('aria-label', 'Fechar menu');
    overlay.hidden = false;
    document.body.classList.add('nav-open');

    var focusable = getFocusable();
    if (focusable.length) {
      focusable[0].focus();
    } else {
      nav.focus();
    }
  }

  function closeNav(returnFocus) {
    if (!isOpen) {
      return;
    }

    isOpen = false;
    nav.classList.remove('is-open');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-label', 'Abrir menu');
    overlay.hidden = true;
    document.body.classList.remove('nav-open');

    if (returnFocus !== false && lastFocused && lastFocused.focus) {
      lastFocused.focus();
    }
  }

  toggle.addEventListener('click', function () {
    if (isOpen) {
      closeNav();
    } else {
      openNav();
    }
  });

  if (closeButton) {
    closeButton.addEventListener('click', function () {
      closeNav();
    });
  }

  overlay.addEventListener('click', function () {
    closeNav();
  });

  nav.addEventListener('click', function (event) {
    if (event.target.closest('a[href]')) {
      closeNav(false);
    }
  });

  document.addEventListener('keydown', function (event) {
    if (!isOpen) {
      return;
    }

    if (event.key === 'Escape') {
      event.preventDefault();
      closeNav();
      return;
    }

    if (event.key !== 'Tab') {
      return;
    }

    var focusable = getFocusable();
    if (!focusable.length) {
      return;
    }

    var first = focusable[0];
    var last = focusable[focusable.length - 1];

    if (!nav.contains(document.activeElement)) {
      event.preventDefault();
      first.focus();
      return;
    }

    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  desktopQuery.addEventListener('change', function (event) {
    if (event.matches) {
      closeNav(false);
    }
  });

  if (desktopQuery.matches) {
    closeNav(false);
  }
})();
