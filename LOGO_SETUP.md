# Logo Installation Instructions

## Adding the BranchSynch Logo

To complete the logo integration, please follow these steps:

1. **Create the static/images directory** (if it doesn't exist):

   ```
   mkdir static
   mkdir static/images
   ```

2. **Save the logo file**:

   - Save the provided logo image as `logo.png`
   - Place it in the `static/images/` directory
   - Final path should be: `c:\Users\Alliyah Angela\retail2\static\images\logo.png`

3. **Logo specifications**:

   - Format: PNG (with transparency)
   - Recommended size: 64x64 pixels or higher
   - The logo will be automatically resized in different contexts

4. **Where the logo appears**:
   - Navigation bar (32x32 pixels)
   - Login page (80x80 pixels)
   - All pages will automatically use the logo

## Alternative: Using Base64 Embedded Logo

If you prefer to embed the logo directly in the templates without external files, the templates can be updated to use a base64-encoded version of the logo.

## Logo Usage

The logo has been integrated into:

- ✅ Navigation header (with BranchSynch text)
- ✅ Login page (larger version)
- ✅ Responsive sizing for different screen sizes
- ✅ Proper alt text for accessibility

Once you place the logo.png file in the static/images/ directory, the website will display your custom BranchSynch logo throughout the application.
