// This file is part of Indico.
// Copyright (C) 2002 - 2024 CERN
//
// Indico is free software; you can redistribute it and/or
// modify it under the terms of the MIT License; see the
// LICENSE file for more details.

import './ind_bypass_block_links.scss';

customElements.define(
  'ind-bypass-block-links',
  class extends HTMLElement {
    connectedCallback() {
      window.addEventListener('DOMContentLoaded', () => {
        const bypassBlockTargets = document.querySelectorAll('[id][data-bypass-target]');
        for (const target of bypassBlockTargets) {
          this.append(
            Object.assign(document.createElement('a'), {
              href: `#${target.id}`,
              textContent: target.dataset.bypassTarget,
            })
          );
        }
      });
    }
  }
);
