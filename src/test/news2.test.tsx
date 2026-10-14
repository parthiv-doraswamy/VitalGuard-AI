import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { News2DemoCalculator } from '../components/settings/News2DemoCalculator.tsx';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('NEWS2 demo calculator', () => {
  it('submits default Scale 1 data and displays returned component scores', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        score_name: 'NEWS2',
        score_version: 'RCP NEWS2 chart (2017)',
        parameter_scores: {
          respiratory_rate: 0, spo2: 0, supplemental_oxygen: 0,
          systolic_bp: 0, heart_rate: 0, consciousness: 0, temperature: 0,
        },
        total_score: 0,
        spo2_scale: 1,
        supplemental_oxygen: false,
        demo_only: true,
        clinically_validated_implementation: false,
        disclaimer: 'Synthetic demo only.',
      }),
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<News2DemoCalculator />);
    await userEvent.click(screen.getByRole('button', { name: /calculate demo score/i }));
    await waitFor(() => expect(screen.getByText('Total demo score')).toBeInTheDocument());
    expect(screen.getByText('NEWS2')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledOnce();
    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(request.method).toBe('POST');
    const body = JSON.parse(String(request.body));
    expect(body.spo2_scale).toBe(1);
    expect(body.scale2_authorized).toBe(false);
  });

  it('blocks Scale 2 until acknowledgement is checked', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        score_name: 'NEWS2', score_version: 'RCP NEWS2 chart (2017)',
        parameter_scores: { respiratory_rate: 0, spo2: 0, supplemental_oxygen: 0, systolic_bp: 0, heart_rate: 0, consciousness: 0, temperature: 0 },
        total_score: 0, spo2_scale: 2, supplemental_oxygen: false,
        demo_only: true, clinically_validated_implementation: false, disclaimer: 'Synthetic demo only.',
      }),
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<News2DemoCalculator />);
    await user.selectOptions(screen.getByLabelText('SpO₂ scoring scale'), '2');
    expect(screen.getByText(/this checkbox is not proof of authorization/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /calculate demo score/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/Scale 2 requires an explicit acknowledgement/i);
    expect(fetchMock).not.toHaveBeenCalled();
    await user.click(screen.getByRole('checkbox', { name: /Scale 2 authorization assertion/i }));
    await user.click(screen.getByRole('button', { name: /calculate demo score/i }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    expect(JSON.parse(String(fetchMock.mock.calls[0][1].body)).scale2_authorized).toBe(true);
  });
});
