(function () {
  'use strict';

  var nav = document.getElementById('app-nav');
  var toggle = document.getElementById('nav-toggle');
  var closeButton = document.getElementById('nav-close');
  var overlay = document.getElementById('nav-overlay');
  var searchToggle = document.getElementById('search-toggle');
  var searchPanel = document.getElementById('app-search-panel');
  var searchInput = document.getElementById('global-search');
  var searchResults = document.getElementById('global-search-results');

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

  function openSearch() {
    if (!searchPanel || !searchToggle) {
      return;
    }

    closeNav(false);
    searchPanel.classList.add('is-open');
    searchToggle.setAttribute('aria-expanded', 'true');
    searchToggle.setAttribute('aria-label', 'Fechar pesquisa');
    if (searchInput) {
      searchInput.focus();
    }
  }

  function closeSearch(returnFocus) {
    if (!searchPanel || !searchToggle) {
      return;
    }

    searchPanel.classList.remove('is-open');
    searchToggle.setAttribute('aria-expanded', 'false');
    searchToggle.setAttribute('aria-label', 'Abrir pesquisa');
    if (searchResults) {
      searchResults.innerHTML = '';
    }
    if (returnFocus !== false) {
      searchToggle.focus();
    }
  }

  function openNav() {
    if (isOpen) {
      return;
    }

    closeSearch(false);
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

  if (searchToggle) {
    searchToggle.addEventListener('click', function () {
      if (searchPanel && searchPanel.classList.contains('is-open')) {
        closeSearch();
      } else {
        openSearch();
      }
    });
  }

  document.addEventListener('keydown', function (event) {
    if (
      event.key === 'Escape' &&
      searchPanel &&
      searchPanel.classList.contains('is-open')
    ) {
      event.preventDefault();
      closeSearch();
    }
  });

  document.addEventListener('click', function (event) {
    if (
      searchPanel &&
      searchPanel.classList.contains('is-open') &&
      !searchPanel.contains(event.target) &&
      event.target !== searchToggle
    ) {
      closeSearch(false);
      return;
    }

    if (searchResults && searchPanel && !searchPanel.contains(event.target)) {
      searchResults.innerHTML = '';
    }
  });

  Array.prototype.forEach.call(
    document.querySelectorAll('[data-filter-toggle]'),
    function (button) {
      var target = document.getElementById(button.getAttribute('aria-controls'));
      if (!target) {
        return;
      }

      button.addEventListener('click', function () {
        var isExpanded = target.classList.toggle('is-open');
        button.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
      });
    }
  );

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
