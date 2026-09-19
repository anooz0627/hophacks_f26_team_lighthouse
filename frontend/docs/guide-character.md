# Guide character

The website displays three individual character cutouts in `public/guide/`: `rest-cutout.png`, `review-cutout.png` and `guide-cutout.png`. The character has pearl white and charcoal materials, a lime strap with a vertical black buckle, a compact backpack and compass. Each 1024px PNG has alpha transparency and padding around the complete silhouette. `GuideVisual` displays the full image with `object-fit: contain`; Next.js serves responsive optimized images.

The widget uses rendered images and CSS transitions. It does not require a real-time 3D model or additional rendering dependencies.

## State behavior

- Idle, input and warnings: seated dog, eyes visible, ears lowered.
- Review your details: standing robot pose, ears upright and visor closed. It stays visible until the user leaves review, including when a detail is still unknown.
- Understanding, planning and replanning: the same visor pose. Fast API responses are not artificially delayed to display an animation.
- Ready and completed: the forward-stepping pose.
- API errors take precedence over the review pose and keep the existing error message and recovery actions.

`app/page.tsx` passes the actual review phase to `Assistant`; `lib/guide.ts` selects the presentation pose. The widget does not infer the phase from message text, inspect user input or change planning logic. The guide's existing English messages and live region remain intact.

Hide character keeps all guide text. Pause motion and system reduced motion disable the 180ms entrance transition while allowing the appropriate state image to change. There is no continuous animation, canvas, GPU renderer or model-download dependency in the displayed widget.

The artwork viewport is 176px on desktop and 112px on narrow screens. There are no sheet offsets, clipping masks, baked backgrounds or neighboring poses. A small CSS ground shadow sits beneath the character. No reference photographs or screenshot filenames are shipped.
