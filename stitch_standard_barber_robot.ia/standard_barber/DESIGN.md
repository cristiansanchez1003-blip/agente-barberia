---
name: Standard Barber
colors:
  surface: '#0f131c'
  surface-dim: '#0f131c'
  surface-bright: '#353943'
  surface-container-lowest: '#0a0e17'
  surface-container-low: '#181b25'
  surface-container: '#1c1f29'
  surface-container-high: '#262a34'
  surface-container-highest: '#31353f'
  on-surface: '#dfe2ef'
  on-surface-variant: '#e5bcc5'
  inverse-surface: '#dfe2ef'
  inverse-on-surface: '#2c303a'
  outline: '#ac878f'
  outline-variant: '#5c3f46'
  surface-tint: '#ffb1c4'
  primary: '#ffb1c4'
  on-primary: '#65002e'
  primary-container: '#ff4a8d'
  on-primary-container: '#590028'
  inverse-primary: '#ba005b'
  secondary: '#fabc4c'
  on-secondary: '#432c00'
  secondary-container: '#bd8717'
  on-secondary-container: '#3a2600'
  tertiary: '#bfc6dc'
  on-tertiary: '#293041'
  tertiary-container: '#8a90a5'
  on-tertiary-container: '#23293a'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffd9e1'
  primary-fixed-dim: '#ffb1c4'
  on-primary-fixed: '#3f001a'
  on-primary-fixed-variant: '#8f0044'
  secondary-fixed: '#ffdeac'
  secondary-fixed-dim: '#fabc4c'
  on-secondary-fixed: '#281900'
  on-secondary-fixed-variant: '#604100'
  tertiary-fixed: '#dce2f9'
  tertiary-fixed-dim: '#bfc6dc'
  on-tertiary-fixed: '#141b2b'
  on-tertiary-fixed-variant: '#404758'
  background: '#0f131c'
  on-background: '#dfe2ef'
  surface-variant: '#31353f'
typography:
  display:
    fontFamily: Poppins
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Poppins
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Poppins
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
  headline-md:
    fontFamily: Poppins
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  title-lg:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.05em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.1em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  xxl: 48px
  container-margin: 20px
  gutter: 16px
---

## Brand & Style

The design system embodies a **Cyberpunk Luxury** aesthetic—a fusion of high-end craftsmanship and futuristic digital intelligence. It targets a discerning clientele who values both the heritage of grooming and the efficiency of modern technology. 

The visual narrative is defined by:
- **Atmospheric Depth:** Utilizing deep, dark foundations to make interactive elements feel like luminous projections.
- **Precision & Polish:** A mix of sharp digital neon accents with the refined elegance of champagne gold.
- **Glassmorphism:** Surfaces are treated as semi-transparent panels, suggesting a sophisticated, multi-layered digital interface.
- **Emotional Response:** The UI should feel exclusive, high-tech, and authoritative, evoking the feeling of entering a premium, tech-forward lounge.

## Colors

The palette is anchored in a high-contrast dark mode to emphasize luxury and focus.

- **Base:** `#090D16` is used for the primary background. Subtle radial gradients of this color should be used to create depth, avoiding flat black.
- **Primary (Electric Magenta):** `#FF007F` is the "Digital Spirit" accent. Use this for high-priority actions, AI-driven notifications, and active states. It should often be accompanied by a soft glow effect.
- **Secondary (Champagne Gold):** `#E5A93B` represents the "Standard" of excellence. Use this for Barber names, VIP services, and luxury iconography to ground the cyberpunk aesthetic in traditional elegance.
- **Surface:** `#131A2A` acts as the container fill, always applied with a degree of transparency and background blur.
- **Support:** Use slate-800 (`#1E293B`) at 40% opacity for borders and dividers to maintain a subtle, "etched-in-glass" look.

## Typography

The typographic hierarchy balances impact and utility. 

- **Headlines:** Use **Poppins** for all major headings and service titles. Its geometric structure provides the "architectural" feel required for a premium brand. Use tighter letter-spacing for large display text to enhance the bold, cinematic look.
- **Body & Controls:** Use **Inter** for all functional text, descriptions, and buttons. Its high x-height ensures legibility against dark, blurred backgrounds. 
- **Labels:** Small labels and overlines should use **Inter** with increased letter-spacing and uppercase styling to mimic technical HUD (Heads-Up Display) interfaces.
- **Color Application:** Headings should predominantly be White (#FFFFFF) or Champagne Gold for names. Body text should use a slightly muted off-white (#E2E8F0) to reduce eye strain.

## Layout & Spacing

This design system prioritizes a **Mobile-First, Fluid Layout** designed for one-handed operation in a fast-paced environment.

- **Grid:** Use a 4-column fluid grid for mobile and a 12-column grid for desktop views. 
- **Horizontal Flow:** Implement horizontal scroll lists for barber profiles and time-slot selection to maximize vertical real estate.
- **Rhythm:** Spacing follows a 4px base unit. Use `lg` (24px) for section padding and `md` (16px) for internal card padding.
- **Safe Areas:** Ensure interactive elements maintain a 44px minimum hit area, especially for booking flows.

## Elevation & Depth

Visual hierarchy is achieved through **Glassmorphism and Luminous Shadows** rather than traditional grey-scale shadows.

- **Base Layer:** The deepest layer (#090D16) with subtle radial gradients of #131A2A.
- **Surface Layer:** Semi-transparent containers (#131A2A at 60-80% opacity) with a `backdrop-blur` of 12px to 20px. 
- **Borders:** All surfaces must have a 1px border of Slate-800 at 40% opacity to define the edge against dark backgrounds.
- **Neon Glow:** Primary action elements (buttons/active chips) use an outer glow (drop-shadow) using the Electric Magenta hex at 30-50% opacity with a high blur radius (15px-20px) to simulate light emission.

## Shapes

The shape language is "Soft-Tech"—modern and approachable but structurally sound.

- **Standard Radius:** 0.5rem (8px) for cards and primary buttons.
- **Large Radius:** 1rem (16px) for bottom sheets and main container wrappers.
- **Interactive Elements:** Use the standard radius for inputs and selection chips. 
- **Icons:** Icons should feature a consistent 2px stroke weight with slightly rounded terminals to match the typography.

## Components

- **Buttons:** 
    - *Primary:* Electric Magenta background, white text, with a 20px neon glow on hover/active.
    - *Secondary:* Transparent with a 1px Champagne Gold border and Gold text.
- **Glassmorphic Cards:** Used for barber profiles and service descriptions. Must include `backdrop-blur-md`, a 1px border-slate-800/40, and a subtle inner-shadow to give the glass thickness.
- **Horizontal Scroll Lists:** Used for "Select a Barber" and "Available Dates." Items should have a clear "Selected" state using an Electric Magenta border.
- **Input Fields:** Dark fill (#06090F), subtle border, and Champagne Gold focus rings. Labels should be small, uppercase, and placed above the field.
- **Status Indicators:** Use pulsing Electric Magenta dots for "Live" or "AI-Optimized" booking suggestions.
- **Chips:** For time slots, use a "Glass" chip that turns Electric Magenta when selected.