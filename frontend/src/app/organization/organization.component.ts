import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { OrganizationService } from '../services/organization/organization.service';
import { Organization } from '../common/models/organization.model';
import { Observable, tap } from 'rxjs';
import { MatDialog } from '@angular/material/dialog';
import { ImageSelectorComponent } from '../common/components/image-selector/image-selector.component';
import { AssetTypeEnum } from '../admin/source-assets-management/source-asset.model';
import { SourceAssetResponseDto } from '../common/services/source-asset.service';
import { MatSnackBar } from '@angular/material/snack-bar';

@Component({
  selector: 'app-organization',
  templateUrl: './organization.component.html',
  styleUrls: ['./organization.component.scss']
})
export class OrganizationComponent implements OnInit {
  organization$: Observable<Organization> | undefined;
  isEditing = false;
  
  // Form data
  editName = '';
  editDescription = '';
  editLogo = '';

  constructor(
    private route: ActivatedRoute,
    private organizationService: OrganizationService,
    private dialog: MatDialog,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit(): void {
    this.loadOrganization();
  }

  loadOrganization(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.organization$ = this.organizationService.getOrganization(Number(id)).pipe(
        tap(org => {
          this.editName = org.name;
          this.editDescription = org.description || '';
          this.editLogo = org.logo || '';
        })
      );
    }
  }

  toggleEdit(): void {
    this.isEditing = !this.isEditing;
    if (!this.isEditing) {
      // Reset form if cancelling
      this.loadOrganization();
    }
  }

  openLogoSelector(orgId: number): void {
    const dialogRef = this.dialog.open(ImageSelectorComponent, {
      width: '90vw',
      height: '80vh',
      maxWidth: '90vw',
      data: {
        mimeType: 'image/*',
        assetType: AssetTypeEnum.GENERIC_IMAGE
      }
    });

    dialogRef.afterClosed().subscribe((result: SourceAssetResponseDto | any) => {
      if (result) {
        // Handle both direct upload (SourceAssetResponseDto) and gallery selection
        // FIX: Use gcsUri instead of gcsPath
        const url = result.gcsUri || result.mediaItem?.gcsUri;
        
        if (url) {
          this.editLogo = url;
          
          // Immediate save as requested
          this.organizationService.updateOrganization(orgId, { logo: url }).subscribe({
            next: () => {
              this.snackBar.open('Logo updated successfully', 'Close', { duration: 3000 });
              // We also need to update the local organization state to reflect the new logo in non-edit mode if we were to switch back
              // But since we reload on toggle, it should be fine. 
              // However, let's reload it now to be safe and consistent
              this.loadOrganization();
            },
            error: (err) => {
              console.error('Failed to update logo', err);
              this.snackBar.open('Failed to update logo', 'Close', { duration: 3000 });
            }
          });
        }
      }
    });
  }

  saveChanges(orgId: number): void {
    const updateData = {
      name: this.editName,
      description: this.editDescription,
      logo: this.editLogo
    };

    this.organizationService.updateOrganization(orgId, updateData).subscribe({
      next: (updatedOrg) => {
        this.isEditing = false;
        this.loadOrganization(); // Reload to refresh view
        this.snackBar.open('Organization updated successfully', 'Close', { duration: 3000 });
      },
      error: (err) => {
        console.error('Failed to update organization', err);
        this.snackBar.open('Failed to update organization', 'Close', { duration: 3000 });
      }
    });
  }
}
