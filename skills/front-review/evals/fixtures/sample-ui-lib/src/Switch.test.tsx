import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';
import { Switch } from './Switch';

function Harness() {
  const [on, setOn] = useState(false);
  return (
    <Switch checked={on} onCheckedChange={setOn}>
      Notifications
    </Switch>
  );
}

describe('Switch', () => {
  it('flips aria-checked when the user clicks it', async () => {
    render(<Harness />);
    const control = screen.getByRole('switch', { name: 'Notifications' });
    expect(control.getAttribute('aria-checked')).toBe('false');
    await userEvent.click(control);
    expect(control.getAttribute('aria-checked')).toBe('true');
  });
});
