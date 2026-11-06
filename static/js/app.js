(function () {
  'use strict';

  var nav = document.getElementById('app-nav');
  var toggle = document.getElementById('nav-toggle');
  var closeButton = document.getElementById('nav-close');
  var overlay = document.getElementById('nav-overlay');
  var searchPanel = document.getElementById('app-search-panel');
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

  document.addEventListener('click', function (event) {
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

  function initWizard(wizard) {
    var steps = Array.prototype.slice.call(
      wizard.querySelectorAll('[data-step]')
    );
    if (!steps.length) {
      return;
    }

    var indicators = Array.prototype.slice.call(
      wizard.querySelectorAll('[data-step-indicator]')
    );
    var nextButtons = wizard.querySelectorAll('[data-wizard-next]');
    var backButtons = wizard.querySelectorAll('[data-wizard-back]');
    var summary = wizard.querySelector('[data-wizard-summary]');
    var current = parseInt(wizard.getAttribute('data-initial-step'), 10);

    if (isNaN(current) || current < 1) {
      current = 1;
    }
    if (current > steps.length) {
      current = steps.length;
    }

    function updateSummary() {
      if (!summary) {
        return;
      }

      summary.innerHTML = '';
      var fields = steps[0].querySelectorAll('input, select, textarea');

      Array.prototype.forEach.call(fields, function (field) {
        if (
          field.type === 'hidden' ||
          field.type === 'button' ||
          field.type === 'submit' ||
          field.disabled ||
          !field.value
        ) {
          return;
        }

        var label = field.id
          ? wizard.querySelector('label[for="' + field.id + '"]')
          : null;
        var labelText = label
          ? label.textContent.trim().replace(/:\s*$/, '')
          : field.name;
        var value = field.value;

        if (field.tagName === 'SELECT' && field.selectedIndex >= 0) {
          value = field.options[field.selectedIndex].text;
        } else if (field.type === 'date' && value.indexOf('-') !== -1) {
          var dateParts = value.split('-');
          value = dateParts[2] + '/' + dateParts[1] + '/' + dateParts[0];
        }

        var item = document.createElement('div');
        item.className = 'wizard-summary-item';

        var labelElement = document.createElement('span');
        labelElement.textContent = labelText;

        var valueElement = document.createElement('strong');
        valueElement.textContent = value;

        item.appendChild(labelElement);
        item.appendChild(valueElement);
        summary.appendChild(item);
      });
    }

    function updateProgress() {
      Array.prototype.forEach.call(indicators, function (indicator) {
        var stepNumber = parseInt(
          indicator.getAttribute('data-step-indicator'),
          10
        );
        indicator.classList.toggle('is-active', stepNumber === current);
        indicator.classList.toggle('is-complete', stepNumber < current);

        if (stepNumber === current) {
          indicator.setAttribute('aria-current', 'step');
        } else {
          indicator.removeAttribute('aria-current');
        }
      });
    }

    function showStep(stepNumber, focus) {
      if (stepNumber < 1) {
        stepNumber = 1;
      }
      if (stepNumber > steps.length) {
        stepNumber = steps.length;
      }

      current = stepNumber;
      wizard.setAttribute('data-current-step', String(current));

      Array.prototype.forEach.call(steps, function (step) {
        var number = parseInt(step.getAttribute('data-step'), 10);
        step.classList.toggle('is-active', number === current);
      });

      updateProgress();
      if (current === 2) {
        updateSummary();
      }

      if (focus) {
        var active = wizard.querySelector('.wizard-step.is-active');
        var firstField = active
          ? active.querySelector(
              'input:not([type="hidden"]), select, textarea, button'
            )
          : null;

        if (firstField) {
          firstField.focus();
        }
        wizard.scrollIntoView({ block: 'start' });
      }
    }

    function validateCurrentStep() {
      var active = wizard.querySelector('.wizard-step.is-active');
      if (!active) {
        return true;
      }

      var fields = active.querySelectorAll('input, select, textarea');
      for (var index = 0; index < fields.length; index += 1) {
        var field = fields[index];
        if (
          field.disabled ||
          field.type === 'hidden' ||
          field.type === 'button' ||
          field.type === 'submit'
        ) {
          continue;
        }
        if (!field.checkValidity()) {
          field.reportValidity();
          return false;
        }
      }

      return true;
    }

    Array.prototype.forEach.call(nextButtons, function (button) {
      button.addEventListener('click', function () {
        if (validateCurrentStep()) {
          showStep(current + 1, true);
        }
      });
    });

    Array.prototype.forEach.call(backButtons, function (button) {
      button.addEventListener('click', function () {
        showStep(current - 1, true);
      });
    });

    wizard.addEventListener('keydown', function (event) {
      if (event.key !== 'Enter' || event.shiftKey) {
        return;
      }
      if (
        event.target.tagName === 'TEXTAREA' ||
        event.target.tagName === 'BUTTON' ||
        event.target.tagName === 'A'
      ) {
        return;
      }
      if (current === 1 && steps.length > 1) {
        event.preventDefault();
        if (validateCurrentStep()) {
          showStep(2, true);
        }
      }
    });

    if (summary) {
      steps[0].addEventListener('input', updateSummary);
      steps[0].addEventListener('change', updateSummary);
    }

    wizard.setAttribute('data-ready', 'true');
    showStep(current, false);
  }

  Array.prototype.forEach.call(
    document.querySelectorAll('[data-wizard]'),
    initWizard
  );
})();
(function () {
  'use strict';

  var currency = new Intl.NumberFormat('pt-PT', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });

  function parseNumber(value) {
    var parsed = parseFloat(value);
    return isNaN(parsed) ? null : parsed;
  }

  function roundCents(value) {
    return Math.round(value * 100) / 100;
  }

  function formatMoney(value) {
    return currency.format(value) + ' €';
  }

  function updateTotals(form) {
    var total = 0;
    var hasSubtotal = false;
    var lines = form.querySelectorAll('[data-purchase-line]');

    Array.prototype.forEach.call(lines, function (line) {
      var quantityField = line.querySelector('[name$="-quantity"]');
      var priceField = line.querySelector('[name$="-unit_price"]');
      var deleteField = line.querySelector('[name$="-DELETE"]');
      var output = line.querySelector('[data-line-subtotal]');
      var quantity = quantityField ? parseNumber(quantityField.value) : null;
      var price = priceField ? parseNumber(priceField.value) : null;
      var removed = deleteField && deleteField.checked;
      var subtotal = null;

      if (!removed && quantity !== null && price !== null) {
        subtotal = roundCents(quantity * price);
        total += subtotal;
        hasSubtotal = true;
      }

      if (output) {
        output.textContent = subtotal === null ? '—' : formatMoney(subtotal);
      }
    });

    var target = form.querySelector('[data-purchase-total]');
    if (target) {
      target.textContent = hasSubtotal
        ? formatMoney(roundCents(total))
        : '—';
    }
  }

  function refresh() {
    Array.prototype.forEach.call(
      document.querySelectorAll('[data-purchase-totals]'),
      updateTotals
    );
  }

  function isInsidePurchaseForm(event) {
    return (
      event.target &&
      event.target.closest &&
      event.target.closest('[data-purchase-totals]')
    );
  }

  document.addEventListener('input', function (event) {
    if (isInsidePurchaseForm(event)) {
      refresh();
    }
  });

  document.addEventListener('change', function (event) {
    if (isInsidePurchaseForm(event)) {
      refresh();
    }
  });

  document.addEventListener('htmx:afterSwap', refresh);

  refresh();
})();
(function () {
  'use strict';

  var DISCRETE_UNITS = ['un', 'cx', 'sc', 'pl', 'rl', 'pct', 'md'];

  function quantityInputFor(select) {
    var row = select.closest('[data-purchase-line]');
    if (row) {
      return row.querySelector('input[name$="-quantity"]');
    }

    var form = select.closest('form');
    return form ? form.querySelector('input[name="quantity"]') : null;
  }

  function syncQuantityStep(select) {
    var input = quantityInputFor(select);
    if (!input) {
      return;
    }

    var option = select.options[select.selectedIndex];
    var unit = option ? option.getAttribute('data-unit') : null;
    var discrete = Boolean(unit) && DISCRETE_UNITS.indexOf(unit) !== -1;

    input.setAttribute('step', discrete ? '1' : '0.001');
    input.setAttribute('min', discrete ? '1' : '0.001');
  }

  function syncAllQuantitySteps() {
    Array.prototype.forEach.call(
      document.querySelectorAll('select.item-select'),
      syncQuantityStep
    );
  }

  function applyQuickItem(marker) {
    var prefix = marker.getAttribute('data-prefix');
    var itemId = marker.getAttribute('data-item-id');
    var label = marker.getAttribute('data-item-label');

    if (!prefix || !itemId) {
      marker.remove();
      return;
    }

    var select = document.getElementById('id_' + prefix + '-item');
    if (select) {
      var option = document.createElement('option');
      option.value = itemId;
      option.textContent = label;
      option.setAttribute('data-unit', marker.getAttribute('data-item-unit') || '');
      select.appendChild(option);
      select.value = itemId;
      select.dispatchEvent(new Event('change', { bubbles: true }));
    }

    var status = document.getElementById(prefix + '-quick-status');
    if (status) {
      status.textContent = '“' + label + '” foi criado e selecionado nesta linha.';
    }

    marker.remove();
  }

  function handleQuickItems() {
    Array.prototype.forEach.call(
      document.querySelectorAll('[data-quick-item-created]'),
      applyQuickItem
    );
  }

  document.addEventListener('change', function (event) {
    if (event.target.matches && event.target.matches('select.item-select')) {
      syncQuantityStep(event.target);
    }
  });

  document.addEventListener('htmx:afterSwap', function () {
    handleQuickItems();
    syncAllQuantitySteps();
  });

  document.addEventListener('click', function (event) {
    var cancel = event.target.closest
      ? event.target.closest('[data-quick-cancel]')
      : null;

    if (!cancel) {
      return;
    }

    var form = cancel.closest('.quick-item-form');
    if (!form) {
      return;
    }

    var row = form.closest('[data-purchase-line]');
    var status = row ? row.querySelector('[id$="-quick-status"]') : null;
    if (status) {
      status.textContent = '';
    }

    form.remove();
  });

  handleQuickItems();
  syncAllQuantitySteps();
})();
